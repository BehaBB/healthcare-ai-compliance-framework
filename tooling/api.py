from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import uuid
import logging
from pathlib import Path
import sys
import json
from datetime import datetime
from pathlib import Path

# Добавляем путь, чтобы можно было импортировать из tooling
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импортируем наш новый детектор
from tooling.phi_detector import PresidioPHIDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Healthcare AI Compliance Framework - Presidio Edition")

# Инициализация Presidio детектора
phi_detector = PresidioPHIDetector()

class ProcessRequest(BaseModel):
    input_text: str

class ComplianceResponse(BaseModel):
    compliant: bool
    risk_level: str
    blocked_phi: bool
    reasons: list[str]
    processed_text: str
    phi_detected_entities: list[str] = []
    trace_id: str

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Healthcare AI Compliance Framework with Presidio is running"}

@app.post("/process", response_model=ComplianceResponse)
def process_input(request: ProcessRequest):
    text = request.input_text.strip()
    trace_id = str(uuid.uuid4())[:8]

    try:
        # PROFESSIONAL PHI DETECTION WITH PRESIDIO
        phi_result = phi_detector.detect_phi(text)
        has_phi = phi_result["phi_found"]
        phi_entities = [e["entity_type"] for e in phi_result["entities"]]

        # Анонимизация
        redacted_text, anon_info = phi_detector.anonymize_text(text)

        # === УЛУЧШЕННАЯ ЛОГИКА ОЦЕНКИ РИСКА ===
        critical_phi = ["PERSON", "US_SSN", "PHONE_NUMBER", "EMAIL_ADDRESS"]
        sensitive_phi = ["DATE_TIME", "LOCATION"]

        critical_count = sum(1 for e in phi_entities if e in critical_phi)
        sensitive_count = sum(1 for e in phi_entities if e in sensitive_phi)
        medical_count = len([e for e in phi_entities if e == "MEDICAL_TERM"])

        if critical_count >= 1:
            risk_level = "high"
            reasons = [f"High risk: Critical PHI detected ({', '.join([e for e in phi_entities if e in critical_phi])})"]
        elif critical_count == 0 and sensitive_count >= 2:
            risk_level = "high"
            reasons = ["High risk: Multiple sensitive PHI elements (name + date/location)"]
        elif sensitive_count >= 1 or medical_count >= 3:
            risk_level = "medium"
            reasons = [f"Medium risk: PHI detected ({', '.join(phi_entities)})"]
        else:
            risk_level = "low"
            reasons = ["Compliant: No significant Protected Health Information detected"]

        compliant = risk_level == "low"

        result = {
            "compliant": compliant,
            "risk_level": risk_level,
            "blocked_phi": has_phi,
            "reasons": reasons,
            "processed_text": redacted_text if has_phi else text,
            "phi_detected_entities": phi_entities,
            "trace_id": trace_id,
            "anonymization_info": {
                "entities_redacted": len(phi_entities),
                "original_text_length": len(text),
                "redacted_text_length": len(redacted_text)
            }
        }

        logger.info(f"Trace {trace_id} | Risk: {risk_level} | PHI: {has_phi} | Entities: {phi_entities}")
                # Записываем аудит
        write_audit_log(
            trace_id=trace_id,
            original_text=text,
            result=result,
            risk_level=risk_level,
            phi_entities=phi_entities
        )
        
        return result
        

    except Exception as e:
        logger.error(f"Error processing trace {trace_id}: {str(e)}")
        return {
            "compliant": False,
            "risk_level": "high",
            "blocked_phi": False,
            "reasons": ["Internal error during PHI analysis. Please try again."],
            "processed_text": "[PROCESSING ERROR]",
            "phi_detected_entities": [],
            "trace_id": trace_id
        }

        # ==================== AUDIT LOGGING ====================
def write_audit_log(trace_id: str, original_text: str, result: dict, risk_level: str, phi_entities: list):
    """Сохраняет полный аудит каждой обработки запроса"""
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trace_id": trace_id,
            "risk_level": risk_level,
            "blocked_phi": result.get("blocked_phi", False),
            "phi_detected_entities": phi_entities,
            "original_text_length": len(original_text),
            "processed_text_length": len(result.get("processed_text", "")),
            "reasons": result.get("reasons", []),
            "anonymization_info": result.get("anonymization_info", {})
        }

        # Создаём папку, если её нет
        log_dir = Path("audit_logs")
        log_dir.mkdir(exist_ok=True)

        # Сохраняем в отдельный файл по trace_id
        log_file = log_dir / f"audit_{trace_id}.json"
        
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)

        logger.info(f"Audit log saved: audit_{trace_id}.json")
        
    except Exception as e:
        logger.error(f"Failed to write audit log for trace {trace_id}: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)