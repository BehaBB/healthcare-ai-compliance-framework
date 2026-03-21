from tooling.policy_engine import evaluate_policies
from tooling.audit import log_event


def process_request(user_id: str, text: str):

    log_event(user_id, "request_received")

    # 1. применяем policies
    decision = evaluate_policies(text)

    # 2. блокировка
    if decision.get("block"):
        log_event(user_id, "request_blocked")
        return {
            "status": "blocked",
            "reason": decision.get("reason", "policy_violation")
        }

    # 3. allow
    log_event(user_id, "request_allowed")

    return {
        "status": "ok",
        "output": text
    }
