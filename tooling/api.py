from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import re
import logging
import json
import uuid
from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Healthcare AI Compliance Framework")

# ========== Модели ==========
class ProcessRequest(BaseModel):
    input_text: str

class ComplianceResponse(BaseModel):
    compliant: bool
    risk_level: str = "low"
    blocked_phi: bool = False
    reasons: List[str] = []
    processed_text: str = ""
    fda_risk_score: Optional[int] = None
    fda_category: Optional[str] = None
    trace_id: Optional[str] = None

# ========== Audit ==========
AUDIT_LOG_DIR = Path(__file__).parent.parent / "audit_logs"
AUDIT_LOG_DIR.mkdir(exist_ok=True)

def write_audit_log(trace_id: str, request_text: str, response: dict, risk_level: str):
    audit_entry = {
        "trace_id": trace_id,
        "timestamp": datetime.utcnow().isoformat(),
        "request_text": request_text[:500],
        "response": response,
        "risk_level": risk_level,
    }
    log_file = AUDIT_LOG_DIR / f"{datetime.utcnow().date()}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(audit_entry) + "\n")

# ========== PHI Detection ==========
def detect_phi_advanced(text: str) -> tuple[bool, List[str]]:
    reasons = []
    phi_patterns = {
        "PATIENT_NAME": r'\b(?:Patient|Ms\.?|Mr\.?|Dr\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b',
        "DATE_OF_BIRTH": r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b',
        "PHONE_NUMBER": r'\b[\+]?[\d\s-]{10,15}\b',
        "EMAIL": r'\b[\w\.-]+@[\w\.-]+\.\w+\b',
        "MEDICAL_RECORD_NUMBER": r'\b(?:MRN|Medical Record)[:\s]*\d{5,10}\b'
    }
    for phi_type, pattern in phi_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            reasons.append(f"Detected {phi_type}")
    return len(reasons) > 0, reasons

def detect_medical_recommendations(text: str) -> tuple[bool, List[str]]:
    recommendations = []
    risk_patterns = {
        "DRUG_RECOMMENDATION": r'\b(?:recommend|prescribe|take|give)\s+(?:metformin|ibuprofen|aspirin|antibiotic|insulin)\b',
        "DIAGNOSIS": r'\b(?:diagnosed with|has)\s+(?:diabetes|cancer|hypertension)\b',
    }
    for risk_type, pattern in risk_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            recommendations.append(f"Detected {risk_type}")
    return len(recommendations) > 0, recommendations

# ========== FDA Risk Scoring ==========
def calculate_fda_risk_score(text: str, has_phi: bool, has_recommendations: bool) -> dict:
    risk_score = 0
    if has_phi:
        risk_score += 30
    if has_recommendations:
        risk_score += 50
    if re.search(r'\b(diagnosis|treat|cure)\b', text, re.IGNORECASE):
        risk_score += 20
    risk_score = min(risk_score, 100)
    
    if risk_score >= 70:
        fda_category = "III (High Risk)"
    elif risk_score >= 40:
        fda_category = "II (Moderate Risk)"
    else:
        fda_category = "I (Low Risk)"
    
    return {"risk_score": risk_score, "fda_category": fda_category}

# ========== ГЛАВНАЯ ФУНКЦИЯ (улучшенная) ==========
def check_compliance_enhanced(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        return {
            "compliant": False,
            "risk_level": "low",
            "blocked_phi": False,
            "reasons": ["Empty input"],
            "processed_text": "",
            "fda_risk_score": 0,
            "fda_category": "I (Low Risk)",
            "trace_id": str(uuid.uuid4())[:8]
        }
    
    has_phi, phi_reasons = detect_phi_advanced(text)
    has_rec, rec_reasons = detect_medical_recommendations(text)
    fda_risk = calculate_fda_risk_score(text, has_phi, has_rec)
    trace_id = str(uuid.uuid4())[:8]
    
    if has_rec or fda_risk["risk_score"] >= 70:
        result = {
            "compliant": False,
            "risk_level": "high",
            "blocked_phi": has_phi,
            "reasons": phi_reasons + rec_reasons + ["HIGH RISK - Requires physician review"],
            "processed_text": f"[REQUIRES REVIEW] {text[:100]}...",
            "fda_risk_score": fda_risk["risk_score"],
            "fda_category": fda_risk["fda_category"],
            "trace_id": trace_id
        }
    elif has_phi:
        result = {
            "compliant": False,
            "risk_level": "medium",
            "blocked_phi": True,
            "reasons": phi_reasons + ["PHI detected - needs redaction"],
            "processed_text": re.sub(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', '[NAME]', text),
            "fda_risk_score": fda_risk["risk_score"],
            "fda_category": fda_risk["fda_category"],
            "trace_id": trace_id
        }
    else:
        result = {
            "compliant": True,
            "risk_level": "low",
            "blocked_phi": False,
            "reasons": ["Compliant: No issues detected"],
            "processed_text": text,
            "fda_risk_score": fda_risk["risk_score"],
            "fda_category": fda_risk["fda_category"],
            "trace_id": trace_id
        }
    
    write_audit_log(trace_id, text, result, result["risk_level"])
    return result

# ========== ЭНДПОИНТ /process (ОБНОВЛЕН) ==========
@app.post("/process", response_model=ComplianceResponse)
def process_input(request: ProcessRequest):
    """Основной endpoint с расширенным compliance и audit"""
    try:
        logger.info(f"Processing request: {len(request.input_text)} chars")
        result = check_compliance_enhanced(request.input_text)  # ← теперь используем новую!
        logger.info(f"Trace {result.get('trace_id')}: compliant={result['compliant']}")
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

# ========== Дополнительные эндпоинты ==========
@app.get("/")
def root():
    return {"status": "ok", "service": "Healthcare AI Compliance Framework"}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
    
