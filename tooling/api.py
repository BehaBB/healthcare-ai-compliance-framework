from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import re
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в PATH (на случай, если нужно импортировать другие модули)
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Healthcare AI Compliance Framework")

class ProcessRequest(BaseModel):
    input_text: str

class ComplianceResponse(BaseModel):
    compliant: bool
    risk_level: str = "low"
    blocked_phi: bool = False
    reasons: List[str] = []
    processed_text: str = ""

# ========== PHI Detection Functions ==========
def detect_phi_advanced(text: str) -> tuple[bool, List[str]]:
    """
    Расширенное обнаружение PHI с регулярными выражениями
    Соответствует HIPAA PHI identifiers
    """
    reasons = []
    
    # HIPAA 18 identifiers
    phi_patterns = {
        "PATIENT_NAME": r'\b(?:Patient|Ms\.?|Mr\.?|Dr\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b',
        "DATE_OF_BIRTH": r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b',
        "AGE_OVER_89": r'\b(?:9[0-9]|[1-9][0-9]{2})\s*(?:years?|y\.?o\.?)\b',
        "PHONE_NUMBER": r'\b[\+]?[\d\s-]{10,15}\b',
        "EMAIL": r'\b[\w\.-]+@[\w\.-]+\.\w+\b',
        "ADDRESS": r'\b\d{1,5}\s+(?:[A-Za-z]+\s?)+ (?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b',
        "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
        "MEDICAL_RECORD_NUMBER": r'\b(?:MRN|Medical Record)[:\s]*\d{5,10}\b',
        "HEALTH_PLAN_ID": r'\b(?:Policy|Group|Plan)[:\s]*[A-Z0-9]{5,15}\b'
    }
    
    for phi_type, pattern in phi_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            reasons.append(f"Detected {phi_type}")
    
    return len(reasons) > 0, reasons

def detect_medical_recommendations(text: str) -> tuple[bool, List[str]]:
    """
    Обнаружение потенциально опасных медицинских рекомендаций
    """
    recommendations = []
    
    risk_patterns = {
        "DRUG_RECOMMENDATION": r'\b(?:recommend|prescribe|take|give|administer)\s+(?:metformin|ibuprofen|aspirin|antibiotic|opioid|insulin)\b',
        "DOSAGE_INSTRUCTION": r'\b\d+\s*(?:mg|mcg|g|ml|tablets?|capsules?)\b.*?(?:daily|twice|three times|every)',
        "DIAGNOSIS": r'\b(?:diagnosed with|suffering from|has)\s+(?:diabetes|cancer|hypertension|depression|anxiety)\b',
        "TREATMENT_PLAN": r'\b(?:treatment plan|therapy|surgery|procedure|follow-up care)\b'
    }
    
    for risk_type, pattern in risk_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            recommendations.append(f"Detected {risk_type}")
    
    return len(recommendations) > 0, recommendations

def assess_risk_level(text: str, has_phi: bool, phi_reasons: List[str], has_recommendations: bool, rec_reasons: List[str]) -> str:
    """
    Оценка уровня риска на основе обнаруженного контента
    """
    # HIGH RISK: прямые медицинские рекомендации
    if has_recommendations:
        return "high"
    
    # MEDIUM RISK: есть PHI но нет рекомендаций
    if has_phi:
        return "medium"
    
    # LOW RISK: обычный информационный запрос
    return "low"

def check_compliance(text: str) -> Dict[str, Any]:
    """
    Основная функция проверки compliance
    """
    # Проверка пустого ввода
    if not text or not text.strip():
        return {
            "compliant": False,
            "risk_level": "low",
            "blocked_phi": False,
            "reasons": ["Empty input provided"],
            "processed_text": ""
        }
    
    # Детекция PHI
    has_phi, phi_reasons = detect_phi_advanced(text)
    
    # Детекция медицинских рекомендаций
    has_recommendations, rec_reasons = detect_medical_recommendations(text)
    
    # Оценка риска
    risk_level = assess_risk_level(text, has_phi, phi_reasons, has_recommendations, rec_reasons)
    
    # Собираем все причины
    all_reasons = phi_reasons + rec_reasons
    
    # Принимаем решение
    if has_recommendations:
        return {
            "compliant": False,
            "risk_level": risk_level,
            "blocked_phi": has_phi,
            "reasons": all_reasons + ["BLOCKED: Medical recommendations require physician review"],
            "processed_text": "[REQUIRES PHYSICIAN REVIEW] " + text[:100] + "..."
        }
    elif has_phi:
        return {
            "compliant": False,
            "risk_level": risk_level,
            "blocked_phi": True,
            "reasons": all_reasons + ["Contains Protected Health Information - requires redaction"],
            "processed_text": "[PHI REDACTED] " + re.sub(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', '[NAME]', text)
        }
    else:
        return {
            "compliant": True,
            "risk_level": risk_level,
            "blocked_phi": False,
            "reasons": all_reasons if all_reasons else ["Compliant: No PHI or medical recommendations detected"],
            "processed_text": text
        }

# ========== API Endpoints ==========
@app.get("/")
def read_root():
    return {
        "status": "ok",
        "service": "Healthcare AI Compliance Framework",
        "version": "1.0.0",
        "endpoints": ["/process", "/health", "/debug"]
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "compliance-engine"}

@app.post("/process", response_model=ComplianceResponse)
def process_input(request: ProcessRequest):
    """
    Основной endpoint проверки compliance для медицинских AI-запросов
    """
    try:
        logger.info(f"Processing request: {len(request.input_text)} chars")
        result = check_compliance(request.input_text)
        logger.info(f"Result: compliant={result['compliant']}, risk={result['risk_level']}")
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.post("/debug")
def debug_endpoint(request: ProcessRequest):
    """
    Debug endpoint с детальной информацией для отладки
    """
    has_phi, phi_reasons = detect_phi_advanced(request.input_text)
    has_rec, rec_reasons = detect_medical_recommendations(request.input_text)
    risk = assess_risk_level(request.input_text, has_phi, phi_reasons, has_rec, rec_reasons)
    
    return {
        "input_text": request.input_text,
        "input_length": len(request.input_text),
        "has_phi": has_phi,
        "phi_details": phi_reasons,
        "has_medical_recommendations": has_rec,
        "recommendation_details": rec_reasons,
        "risk_level": risk,
        "would_be_blocked": has_rec or has_phi
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
