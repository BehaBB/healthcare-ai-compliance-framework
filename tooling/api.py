from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI(title="Healthcare AI Compliance Framework - Fixed Version")

class ProcessRequest(BaseModel):
    input_text: str

class ComplianceResponse(BaseModel):
    compliant: bool
    risk_level: str = "low"
    blocked_phi: bool = False
    reasons: list[str] = []
    processed_text: str = ""

# Простая проверка PHI с помощью функции, которая точно существует
def check_compliance(text: str):
    has_phi = not no_phi_rule(text)   # используем функцию из policy_engine.py
    if has_phi:
        return {
            "compliant": False,
            "risk_level": "high",
            "blocked_phi": True,
            "reasons": ["Potential Protected Health Information (PHI) detected"],
            "processed_text": "[REDACTED]"
        }
    return {
        "compliant": True,
        "risk_level": "low",
        "blocked_phi": False,
        "reasons": ["No PHI detected"],
        "processed_text": text
    }

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Healthcare AI Compliance Framework is running (fixed version)"}

@app.post("/process")
def process_input(request: ProcessRequest):
    result = check_compliance(request.input_text)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
