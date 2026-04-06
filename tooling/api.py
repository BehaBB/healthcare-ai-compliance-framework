from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import uuid
import logging
from pathlib import Path
import sys

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
        # Используем профессиональный Presidio детектор
        phi_result = phi_detector.detect_phi(text)
        has_phi = phi_result["phi_found"]
        phi_entities = [e["entity_type"] for e in phi_result["entities"]]

        # Анонимизация текста
        redacted_text, anon_info = phi_detector.anonymize_text(text)

        risk_level = phi_result["risk_level"]

        if has_phi:
            result = {
                "compliant": False,
                "risk_level": risk_level,
                "blocked_phi": True,
                "reasons": [f"PHI detected: {', '.join(phi_entities)}"],
                "processed_text": redacted_text,
                "phi_detected_entities": phi_entities,
                "trace_id": trace_id
            }
        else:
            result = {
                "compliant": True,
                "risk_level": "low",
                "blocked_phi": False,
                "reasons": ["No PHI detected"],
                "processed_text": text,
                "phi_detected_entities": [],
                "trace_id": trace_id
            }

        logger.info(f"Trace {trace_id}: Processed with risk_level={risk_level}, PHI={has_phi}")
        return result

    except Exception as e:
        logger.error(f"Error processing request {trace_id}: {str(e)}")
        return {
            "compliant": False,
            "risk_level": "high",
            "blocked_phi": False,
            "reasons": ["Internal error during PHI detection"],
            "processed_text": "[ERROR]",
            "phi_detected_entities": [],
            "trace_id": trace_id
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)