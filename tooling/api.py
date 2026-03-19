from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from policy_loader import YAMLPolicyEngine
from audit import log_event   # 👈 ВОТ СЮДА импорт

app = FastAPI(title="Healthcare AI Compliance API")

engine = YAMLPolicyEngine("tooling/policies.yaml")


class RequestData(BaseModel):
    input_text: str


@app.post("/process")
def process(data: RequestData):
    try:
        engine.validate(data.input_text)

        # ✅ ЛОГ ДОПУЩЕННОГО ЗАПРОСА
        log_event("user1", "request_approved")

    except Exception as e:
        # ✅ ЛОГ ЗАБЛОКИРОВАННОГО ЗАПРОСА
        log_event("user1", f"request_blocked: {str(e)}")

        raise HTTPException(status_code=400, detail="Policy violation")

    return {
        "status": "approved",
        "response": "LLM output placeholder"
    }
