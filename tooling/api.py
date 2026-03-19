from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from policy_engine import PolicyEngine, no_phi_rule

app = FastAPI(title="Healthcare AI Compliance API")

engine = PolicyEngine()
engine.add_rule(no_phi_rule)


class RequestData(BaseModel):
    input_text: str


@app.post("/process")
def process(data: RequestData):
    try:
        engine.validate(data.input_text)
    except Exception:
        raise HTTPException(status_code=400, detail="Policy violation")

    return {
        "status": "approved",
        "response": "LLM output placeholder"
    }
