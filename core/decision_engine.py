# core/decision_engine.py
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    """Результат оценки запроса"""
    decision: str  # ALLOW, BLOCK, REVIEW
    risk_level: str  # low, medium, high, critical
    violations: List[Dict[str, Any]]
    score: int  # 0-100
    trace_id: str
    reasoning: str
    requires_human: bool = False


class ComplianceDecisionEngine:
    """
    Единый оркестратор compliance проверок
    INPUT → LlamaGuard → PHI Detection → Risk Assessment → Audit → DECISION
    """
    
    def __init__(self):
        self.llama_guard = None
        self.phi_detector = None
        self._init_components()
        
    def _init_components(self):
        """Инициализирует компоненты с fallback"""
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
    
    def evaluate(self, text: str, user_id: Optional[str] = None) -> EvaluationResult:
        """
        Главная точка входа для оценки запроса
        """
        trace_id = str(uuid.uuid4())[:8]
        violations = []
        risk_score = 0
        
        # ========== 1. LLAMA GUARD CHECK ==========
        guard_result = self._check_llama_guard(text)
        if guard_result["violations"]:
            violations.extend(guard_result["violations"])
            risk_score += guard_result["risk_score"]
        
        # ========== 2. PHI DETECTION ==========
        phi_result = self._check_phi(text)
        if phi_result["violations"]:
            violations.extend(phi_result["violations"])
            risk_score += phi_result["risk_score"]
        
        # ========== 3. МЕДИЦИНСКИЕ РЕКОМЕНДАЦИИ ==========
        medical_result = self._check_medical_recommendations(text)
        if medical_result["violations"]:
            violations.extend(medical_result["violations"])
            risk_score += medical_result["risk_score"]
        
        # ========== 4. ПРИНЯТИЕ РЕШЕНИЯ ==========
        decision, risk_level, requires_human = self._make_decision(
            violations=violations,
            risk_score=risk_score,
            text=text
        )
        
        # ========== 5. ПОСТРОЕНИЕ РЕЗУЛЬТАТА ==========
        result = EvaluationResult(
            decision=decision,
            risk_level=risk_level,
            violations=violations,
            score=min(risk_score, 100),
            trace_id=trace_id,
            reasoning=self._generate_reasoning(decision, violations),
            requires_human=requires_human
        )
        
        # ========== 6. АУДИТ ==========
        self._audit_log(
            trace_id=trace_id,
            user_id=user_id,
            text=text,
            result=result
        )
        
        return result
    
    def _check_llama_guard(self, text: str) -> Dict[str, Any]:
        """Проверка через Llama Guard"""
        if not self.llama_guard:
            return {"violations": [], "risk_score": 0}
        
        try:
            result = self.llama_guard.check(text)
            if not result["safe"]:
                return {
                    "violations": [{
                        "type": "llama_guard",
                        "category": cat,
                        "message": result["message"]
                    } for cat in result.get("categories", ["unsafe"])],
                    "risk_score": 40 if "jailbreak" in result.get("categories", []) else 25
                }
        except Exception as e:
            logger.error(f"Llama Guard error: {e}")
        
        return {"violations": [], "risk_score": 0}
    
    def _check_phi(self, text: str) -> Dict[str, Any]:
        """Проверка PHI через Presidio"""
        if not self.phi_detector:
            return {"violations": [], "risk_score": 0}
        
        try:
            phi_result = self.phi_detector.detect_phi(text)
            if phi_result["phi_found"]:
                entities = [e["entity_type"] for e in phi_result["entities"]]
                critical_phi = ["PERSON", "US_SSN", "PHONE_NUMBER", "EMAIL_ADDRESS"]
                critical_count = sum(1 for e in entities if e in critical_phi)
                
                risk_score = 30 if critical_count > 0 else 15
                
                return {
                    "violations": [{
                        "type": "phi_detected",
                        "entities": entities,
                        "count": len(entities),
                        "critical": critical_count > 0
                    }],
                    "risk_score": risk_score
                }
        except Exception as e:
            logger.error(f"PHI detection error: {e}")
        
        return {"violations": [], "risk_score": 0}
    
    def _check_medical_recommendations(self, text: str) -> Dict[str, Any]:
        """Проверка медицинских рекомендаций"""
        import re
        medical_patterns = [
            r'\b(?:recommend|prescribe|take|give)\s+(?:metformin|ibuprofen|aspirin|antibiotic|insulin)\b',
            r'\b(?:diagnosed with|has)\s+(?:diabetes|cancer|hypertension)\b'
        ]
        
        violations = []
        for pattern in medical_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append({
                    "type": "medical_recommendation",
                    "pattern": pattern,
                    "message": "Medical recommendation without physician oversight"
                })
        
        risk_score = 50 if violations else 0
        return {"violations": violations, "risk_score": risk_score}
    
    def _make_decision(self, violations: List[Dict], risk_score: int, text: str) -> tuple:
        """Принимает решение на основе всех проверок"""
        
        # Критичные нарушения
        critical_types = ["jailbreak", "llama_guard"]
        has_critical = any(
            v.get("type") in critical_types or v.get("category") in critical_types
            for v in violations
        )
        
        if has_critical:
            return "BLOCK", "critical", False
        
        # High risk: медицинские рекомендации или PHI
        has_medical = any(v.get("type") == "medical_recommendation" for v in violations)
        has_critical_phi = any(v.get("critical") for v in violations if v.get("type") == "phi_detected")
        
        if has_medical:
            return "REVIEW", "high", True  # требует Human-in-the-Loop
        if has_critical_phi:
            return "BLOCK", "high", False
        if risk_score >= 30:
            return "BLOCK", "medium", False
        
        return "ALLOW", "low", False
    
    def _generate_reasoning(self, decision: str, violations: List[Dict]) -> str:
        """Генерирует понятное объяснение решения"""
        if not violations:
            return "All compliance checks passed. Request allowed."
        
        reasons = []
        for v in violations:
            if v.get("type") == "llama_guard":
                reasons.append(v.get("message", "Safety violation detected"))
            elif v.get("type") == "phi_detected":
                entities = v.get("entities", [])
                reasons.append(f"PHI detected: {', '.join(entities)}")
            elif v.get("type") == "medical_recommendation":
                reasons.append("Medical recommendation without physician approval")
        
        if decision == "BLOCK":
            return f"Blocked due to: {'; '.join(reasons)}"
        elif decision == "REVIEW":
            return f"Requires human review: {'; '.join(reasons)}"
        else:
            return "Request allowed"
    
    def _audit_log(self, trace_id: str, user_id: Optional[str], text: str, result: EvaluationResult):
        """Аудит с единым форматом"""
        try:
            log_dir = Path(__file__).parent.parent / "audit_logs"
            log_dir.mkdir(exist_ok=True)
            
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "trace_id": trace_id,
                "user_id": user_id,
                "input_text": text[:500],
                "decision": result.decision,
                "risk_level": result.risk_level,
                "risk_score": result.score,
                "violations": result.violations,
                "reasoning": result.reasoning,
                "requires_human": result.requires_human
            }
            
            log_file = log_dir / f"audit_{trace_id}.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_entry, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Audit | {trace_id} | Decision: {result.decision} | Risk: {result.risk_level}")
        except Exception as e:
            logger.error(f"Audit log error: {e}")