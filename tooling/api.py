# tooling/api.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.decision_engine import ComplianceDecisionEngine, ENGINE_VERSION

app = FastAPI(
    title="Healthcare AI Compliance Framework",
    version=ENGINE_VERSION,
    description="Production-ready compliance decision engine"
)

decision_engine = ComplianceDecisionEngine()

class ProcessRequest(BaseModel):
    input_text: str
    user_id: Optional[str] = None

class ProcessResponse(BaseModel):
    decision: str
    risk_level: str
    risk_score: int
    trace_id: str
    session_id: str
    reasoning: str
    explanation: str
    requires_human: bool
    violations: List[Dict[str, Any]]
    masked_text: str
    engine_version: str
    processing_time_ms: float

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Engine-Version"] = ENGINE_VERSION
    response.headers["X-Processing-Time"] = f"{time.time() - start_time:.3f}s"
    return response

@app.get("/")
def root():
    return {
        "service": "Healthcare AI Compliance Framework",
        "engine_version": ENGINE_VERSION,
        "status": "operational"
    }

@app.post("/process", response_model=ProcessResponse)
def process(request: ProcessRequest):
    result = decision_engine.evaluate(
        text=request.input_text,
        user_id=request.user_id
    )
    
    return {
        "decision": result.decision,
        "risk_level": result.risk_level,
        "risk_score": result.risk_score,
        "trace_id": result.trace_id,
        "session_id": result.session_id,
        "reasoning": result.reasoning,
        "explanation": result.explanation,
        "requires_human": result.requires_human,
        "violations": result.violations,
        "masked_text": result.masked_text,
        "engine_version": result.engine_version,
        "processing_time_ms": result.processing_time_ms
    }

@app.get("/health")
def health():
    return {"status": "healthy", "engine_version": ENGINE_VERSION}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)