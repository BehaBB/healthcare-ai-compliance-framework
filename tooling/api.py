# tooling/api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

# Добавляем путь к core
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.decision_engine import ComplianceDecisionEngine, EvaluationResult

app = FastAPI(title="Healthcare AI Compliance Framework")

# Инициализация decision engine (один раз)
decision_engine = ComplianceDecisionEngine()

class ProcessRequest(BaseModel):
    input_text: str
    user_id: Optional[str] = None

class ProcessResponse(BaseModel):
    decision: str  # ALLOW, BLOCK, REVIEW
    risk_level: str
    risk_score: int
    trace_id: str
    reasoning: str
    requires_human: bool
    violations: list

@app.get("/")
def root():
    return {
        "service": "Healthcare AI Compliance Framework",
        "version": "3.0.0",
        "description": "Compliance Decision Engine with Llama Guard + Presidio"
    }

@app.post("/process", response_model=ProcessResponse)
def process(request: ProcessRequest):
    """
    Единая точка входа для всех запросов
    Вся логика в decision_engine
    """
    result = decision_engine.evaluate(
        text=request.input_text,
        user_id=request.user_id
    )
    
    return {
        "decision": result.decision,
        "risk_level": result.risk_level,
        "risk_score": result.score,
        "trace_id": result.trace_id,
        "reasoning": result.reasoning,
        "requires_human": result.requires_human,
        "violations": result.violations
    }

@app.get("/health")
def health():
    return {"status": "healthy", "engine": "ComplianceDecisionEngine"}

if __name__ == "__main__":
    import uvicorn
