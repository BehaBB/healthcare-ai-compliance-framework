from tooling.policy_loader import YAMLPolicyEngine
from tooling.audit import log_event

engine = YAMLPolicyEngine("tooling/policies.yaml")


def process_request(user_id: str, text: str):

    log_event(user_id, "request_received")

    decision = {
        "decision": "ALLOW",
        "violations": []
    }

    try:
        engine.validate(text)

    except Exception as e:
        decision["decision"] = "BLOCK"
        decision["violations"].append(str(e))

    # 🔥 audit ВСЕГДА после решения
    log_event(user_id, f"decision:{decision['decision']}")

    return decision
