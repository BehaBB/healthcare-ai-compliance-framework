# tooling/api.py
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.decision_engine import ComplianceDecisionEngine, ENGINE_VERSION

app = FastAPI(
    title="Healthcare AI Compliance Framework",
    version=ENGINE_VERSION,
    description="Production-ready compliance decision engine with Policy Management"
)

# Инициализация decision engine
decision_engine = ComplianceDecisionEngine()

# ==================== MODELS ====================
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
    policy_hash: str

class PolicyUpdate(BaseModel):
    enabled: Optional[bool] = None
    version: Optional[str] = None
    description: Optional[str] = None


# ==================== MIDDLEWARE ====================
@app.middleware("http")
async def add_security_headers(request, call_next):
    import time
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Engine-Version"] = ENGINE_VERSION
    response.headers["X-Processing-Time"] = f"{time.time() - start_time:.3f}s"
    return response


# ==================== MAIN ENDPOINTS ====================
@app.get("/")
def root():
    return {
        "service": "Healthcare AI Compliance Framework",
        "engine_version": ENGINE_VERSION,
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "process": "/process",
            "policies": "/policies"
        }
    }

@app.post("/process", response_model=ProcessResponse)
def process(request: ProcessRequest):
    """Основной endpoint для проверки compliance"""
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
        "processing_time_ms": result.processing_time_ms,
        "policy_hash": result.policy_hash
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "engine_version": ENGINE_VERSION,
        "policy_hash": decision_engine.policy_manager.get_policy_hash() if decision_engine.policy_manager else "N/A"
    }


# ==================== POLICY MANAGEMENT ENDPOINTS ====================

def get_policy_manager():
    """Dependency для получения PolicyManager"""
    if not decision_engine.policy_manager:
        raise HTTPException(status_code=503, detail="PolicyManager not available")
    return decision_engine.policy_manager


@app.get("/policies")
def get_all_policies(
    enabled_only: bool = Query(False, description="Вернуть только включённые политики"),
    category: str = Query(None, description="Фильтр по категории (phi, safety, medical...)")
):
    """
    Возвращает все политики с возможностью фильтрации
    """
    manager = get_policy_manager()
    
    if enabled_only:
        policies = manager.get_enabled_policies()
    else:
        policies = manager.get_all_policies()

    if category:
        policies = [p for p in policies if p.category == category]

    return {
        "policies": [p.to_dict() for p in policies],
        "count": len(policies),
        "total_count": len(manager.get_all_policies()),
        "policy_hash": manager.get_policy_hash()
    }


@app.get("/policies/{policy_id}")
def get_policy(policy_id: str):
    """
    Получить одну политику по ID
    """
    manager = get_policy_manager()
    policy = manager.get_policy(policy_id)
    
    if not policy:
        raise HTTPException(
            status_code=404, 
            detail=f"Policy with id '{policy_id}' not found"
        )
    
    return policy.to_dict()


@app.post("/policies/reload")
def reload_policies():
    """
    Перезагрузить все политики из YAML-файлов (hot reload)
    """
    try:
        manager = get_policy_manager()
        manager.reload_policies()
        
        return {
            "status": "success",
            "message": "Policies reloaded successfully",
            "policy_count": len(manager.get_all_policies()),
            "policy_hash": manager.get_policy_hash(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload policies: {str(e)}"
        )


@app.patch("/policies/{policy_id}")
def update_policy(policy_id: str, update: PolicyUpdate):
    """
    Частичное обновление политики
    """
    manager = get_policy_manager()
    policy = manager.get_policy(policy_id)
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if update.enabled is not None:
        policy.enabled = update.enabled
    if update.version:
        policy.version = update.version
    if update.description:
        policy.description = update.description

    policy.modified_at = datetime.utcnow()
    
    # Сохраняем изменения в файл
    manager._save_all_policies()

    return {
        "status": "updated",
        "policy_id": policy_id,
        "policy": policy.to_dict(),
        "new_policy_hash": manager.get_policy_hash()
    }


@app.get("/policies/hash")
def get_policies_hash():
    """Возвращает хеш всех политик — для проверки consistency"""
    manager = get_policy_manager()
    return {
        "policy_hash": manager.get_policy_hash(),
        "policy_count": len(manager.get_all_policies()),
        "enabled_count": len(manager.get_enabled_policies())
    }


@app.get("/policies/categories")
def get_policy_categories():
    """Возвращает все категории политик"""
    manager = get_policy_manager()
    categories = list(set(p.category for p in manager.get_all_policies()))
    return {"categories": sorted(categories)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)