# core/decision_engine.py
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import logging
import json
import re
from pathlib import Path
from enum import Enum
import concurrent.futures
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

# ==================== VERSIONING ====================
ENGINE_VERSION = "2.1.0"
ENGINE_NAME = "Healthcare AI Compliance Decision Engine"

# ==================== CONFIGURATION ====================
COMPONENT_TIMEOUT = 3.0  # seconds

# Risk weights configuration
RISK_WEIGHTS = {
    "llama_guard_jailbreak": 80,
    "llama_guard_unsafe": 70,
    "phi_critical": 90,
    "phi_sensitive": 50,
    "medical_recommendation": 60,
    "timeout": 40,
    "default": 30
}

# Risk level thresholds
RISK_THRESHOLDS = {
    "critical": 85,
    "high": 70,
    "medium": 40,
    "low": 0
}


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Violation:
    type: str
    severity: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    risk_contribution: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "risk_contribution": self.risk_contribution
        }


@dataclass
class EvaluationResult:
    decision: str
    risk_level: str
    risk_score: int
    violations: List[Dict[str, Any]]
    trace_id: str
    session_id: str
    reasoning: str
    explanation: str
    requires_human: bool = False
    masked_text: str = ""
    engine_version: str = ENGINE_VERSION
    processing_time_ms: float = 0.0


# Thread-safe audit logger
class AuditLogger:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._write_lock = threading.Lock()
        log_dir = Path(__file__).parent.parent / "audit_logs"
        log_dir.mkdir(exist_ok=True)
        self.log_file = log_dir / "audit.jsonl"
    
    def log(self, entry: Dict[str, Any]):
        with self._write_lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_with_timeout(func, timeout: float, *args, **kwargs):
    """Безопасный запуск функции с timeout через ThreadPoolExecutor"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.error(f"Timeout after {timeout}s in {func.__name__}")
            return {"timeout": True, "error": "timeout"}


class ComplianceDecisionEngine:
    def __init__(self):
        self.llama_guard = None
        self.phi_detector = None
        self.audit_logger = AuditLogger()
        self._session_counter = defaultdict(int)
        self._init_components()
    
    def _init_components(self):
        try:
            from tooling.llama_guard import LlamaGuard
            self.llama_guard = LlamaGuard()
            logger.info("Llama Guard initialized")
        except Exception as e:
            logger.warning(f"Llama Guard not available: {e}")
        
        try:
            from tooling.phi_detector import PresidioPHIDetector
            self.phi_detector = PresidioPHIDetector()
            logger.info("Presidio PHI detector initialized")
        except Exception as e:
            logger.warning(f"Presidio not available: {e}")
    
    def _get_session_id(self, user_id: Optional[str]) -> str:
        """Генерирует session_id для трекинга"""
        if user_id:
            self._session_counter[user_id] += 1
            return f"{user_id}_{self._session_counter[user_id]}"
        return f"anon_{uuid.uuid4().hex[:8]}"
    
    def evaluate(self, text: str, user_id: Optional[str] = None) -> EvaluationResult:
        import time
        start_time = time.time()
        
        trace_id = str(uuid.uuid4())[:8]
        session_id = self._get_session_id(user_id)
        violations: List[Violation] = []
        
        # 1. Llama Guard check with timeout
        guard_result = self._check_llama_guard_safe(text)
        if guard_result.get("violations"):
            violations.extend(guard_result["violations"])
        
        # 2. PHI detection with timeout
        phi_result = self._check_phi_safe(text)
        if phi_result.get("violations"):
            violations.extend(phi_result["violations"])
        
        # 3. Medical recommendations
        medical_result = self._check_medical_recommendations(text)
        if medical_result.get("violations"):
            violations.extend(medical_result["violations"])
        
        # 4. Calculate risk score (hybrid: max + count bonus)
        risk_score = self._calculate_risk_score_hybrid(violations)
        
        # 5. Mask PHI (always)
        masked_text = self._mask_phi(text)
        
        # 6. Make decision
        decision, risk_level, requires_human = self._make_decision(
            violations=violations,
            risk_score=risk_score
        )
        
        # 7. Explainability
        explanation = self._generate_explanation(decision, risk_score, violations)
        reasoning = self._generate_reasoning(decision, violations)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        result = EvaluationResult(
            decision=decision,
            risk_level=risk_level,
            risk_score=risk_score,
            violations=[v.to_dict() for v in violations],
            trace_id=trace_id,
            session_id=session_id,
            reasoning=reasoning,
            explanation=explanation,
            requires_human=requires_human,
            masked_text=masked_text,
            engine_version=ENGINE_VERSION,
            processing_time_ms=round(processing_time_ms, 2)
        )
        
        self._audit_log(trace_id, session_id, user_id, text, result)
        
        return result
    
    def _check_llama_guard_safe(self, text: str) -> Dict[str, Any]:
        """Safe Llama Guard check with timeout (no asyncio)"""
        if not self.llama_guard:
            return {"violations": []}
        
        def sync_check():
            try:
                return self.llama_guard.check(text)
            except Exception as e:
                logger.error(f"Llama Guard error: {e}")
                return {"safe": True, "error": str(e)}
        
        result = run_with_timeout(sync_check, COMPONENT_TIMEOUT)
        
        if result.get("timeout"):
            return {
                "violations": [Violation(
                    type="timeout",
                    severity=Severity.MEDIUM.value,
                    message="Llama Guard timeout - fallback",
                    details={"component": "llama_guard"},
                    risk_contribution=RISK_WEIGHTS["timeout"]
                )]
            }
        
        if not result.get("safe", True):
            violations = []
            for cat in result.get("categories", ["unsafe"]):
                is_jailbreak = cat == "jailbreak"
                severity = Severity.CRITICAL.value if is_jailbreak else Severity.HIGH.value
                weight_key = "llama_guard_jailbreak" if is_jailbreak else "llama_guard_unsafe"
                
                violations.append(Violation(
                    type="llama_guard",
                    severity=severity,
                    message=result.get("message", "Safety violation"),
                    details={"category": cat},
                    risk_contribution=RISK_WEIGHTS.get(weight_key, 70)
                ))
            return {"violations": violations}
        
        return {"violations": []}
    
    def _check_phi_safe(self, text: str) -> Dict[str, Any]:
        """Safe PHI check with timeout"""
        if not self.phi_detector:
            return {"violations": []}
        
        def sync_check():
            try:
                return self.phi_detector.detect_phi(text)
            except Exception as e:
                logger.error(f"PHI detection error: {e}")
                return {"phi_found": False}
        
        result = run_with_timeout(sync_check, COMPONENT_TIMEOUT)
        
        if result.get("timeout"):
            return {
                "violations": [Violation(
                    type="timeout",
                    severity=Severity.MEDIUM.value,
                    message="PHI detector timeout",
                    details={"component": "phi_detector"},
                    risk_contribution=RISK_WEIGHTS["timeout"]
                )]
            }
        
        if result.get("phi_found"):
            entities = [e["entity_type"] for e in result.get("entities", [])]
            critical_phi = ["PERSON", "US_SSN", "PHONE_NUMBER", "EMAIL_ADDRESS"]
            has_critical = any(e in critical_phi for e in entities)
            
            return {
                "violations": [Violation(
                    type="phi_detected",
                    severity=Severity.HIGH.value if has_critical else Severity.MEDIUM.value,
                    message=f"PHI detected: {', '.join(entities)}",
                    details={"entities": entities, "count": len(entities), "critical": has_critical},
                    risk_contribution=RISK_WEIGHTS["phi_critical"] if has_critical else RISK_WEIGHTS["phi_sensitive"]
                )]
            }
        
        return {"violations": []}
    
    def _check_medical_recommendations(self, text: str) -> Dict[str, Any]:
        medical_patterns = [
            (r'\b(?:recommend|prescribe|take|give)\s+(?:metformin|ibuprofen|aspirin|antibiotic|insulin)\b', "drug_recommendation"),
            (r'\b(?:diagnosed with|has)\s+(?:diabetes|cancer|hypertension)\b', "diagnosis"),
            (r'\b\d+\s*(?:mg|mcg|g|ml)\b.*?\b(?:daily|twice|every)\b', "dosage")
        ]
        
        for pattern, subtype in medical_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return {
                    "violations": [Violation(
                        type="medical_recommendation",
                        severity=Severity.HIGH.value,
                        message="Medical recommendation without physician oversight",
                        details={"subtype": subtype},
                        risk_contribution=RISK_WEIGHTS["medical_recommendation"]
                    )]
                }
        
        return {"violations": []}
    
    def _calculate_risk_score_hybrid(self, violations: List[Violation]) -> int:
        """Hybrid risk score: max + bonus per violation"""
        if not violations:
            return 0
        
        max_score = max(v.risk_contribution for v in violations)
        count_bonus = min(len(violations) * 5, 20)
        
        return min(max_score + count_bonus, 100)
    
    def _mask_phi(self, text: str) -> str:
        if not text:
            return text
        
        masked = text
        masked = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '***-**-****', masked)
        masked = re.sub(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', '[EMAIL]', masked)
        masked = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', masked)
        masked = re.sub(r'\b(?:Patient|Ms\.?|Mr\.?|Dr\.?)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b', '[PATIENT_NAME]', masked)
        masked = re.sub(r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b', '[DOB]', masked)
        
        return masked
    
    def _make_decision(self, violations: List[Violation], risk_score: int) -> Tuple[str, str, bool]:
        has_critical = any(v.severity == Severity.CRITICAL.value for v in violations)
        
        if has_critical:
            return "BLOCK", "critical", False
        elif risk_score >= RISK_THRESHOLDS["critical"]:
            return "BLOCK", "critical", False
        elif risk_score >= RISK_THRESHOLDS["high"]:
            return "BLOCK", "high", False
        elif risk_score >= RISK_THRESHOLDS["medium"]:
            return "REVIEW", "medium", True
        else:
            return "ALLOW", "low", False
    
    def _generate_explanation(self, decision: str, risk_score: int, violations: List[Violation]) -> str:
        if not violations:
            return f"✅ Risk: {risk_score}/100. Decision: {decision}."
        
        texts = []
        for v in violations:
            if v.type == "llama_guard":
                texts.append(f"🚫 {v.severity}: {v.message}")
            elif v.type == "phi_detected":
                entities = v.details.get("entities", [])
                texts.append(f"🔒 {v.severity}: PHI - {', '.join(entities)}")
            elif v.type == "medical_recommendation":
                texts.append(f"⚠️ {v.severity}: {v.message}")
            elif v.type == "timeout":
                texts.append(f"⏱️ {v.severity}: {v.message}")
        
        return f"Risk: {risk_score}/100. Decision: {decision}. Reasons: {'; '.join(texts)}"
    
    def _generate_reasoning(self, decision: str, violations: List[Violation]) -> str:
        if not violations:
            return f"Decision: {decision}"
        
        reasons = [v.message for v in violations]
        return f"{decision} due to: {'; '.join(reasons)}"
    
    def _audit_log(self, trace_id: str, session_id: str, user_id: Optional[str], text: str, result: EvaluationResult):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trace_id": trace_id,
            "session_id": session_id,
            "user_id": user_id,
            "input_text": text[:1000],
            "decision": result.decision,
            "risk_level": result.risk_level,
            "risk_score": result.risk_score,
            "violations": result.violations,
            "reasoning": result.reasoning,
            "explanation": result.explanation,
            "requires_human": result.requires_human,
            "masked_text": result.masked_text[:1000],
            "engine_version": result.engine_version,
            "processing_time_ms": result.processing_time_ms
        }
        self.audit_logger.log(log_entry)
        logger.info(f"Audit | {trace_id} | {session_id} | {result.decision} | {result.risk_score}")