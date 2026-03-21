from tooling.policy_loader import YAMLPolicyEngine
from tooling.audit import log_event

# подключаем твои будущие модули
try:
    from risk.risk_engine import calculate_risk
except:
    def calculate_risk(text):
        return 0.0

try:
    from security.security_checks import check_security
except:
    def check_security(text):
        return True


engine = YAMLPolicyEngine("tooling/policies.yaml")


def process_request(user_id: str, text: str):

    log_event(user_id, "request_received")

    decision = {
        "decision": "ALLOW",
        "violations": [],
        "risk_score": 0.0
    }

    # 🔐 SECURITY
    if not check_security(text):
        decision["decision"] = "BLOCK"
        decision["violations"].append("security_violation")
        log_event(user_id, "blocked_security")
        return decision

    # 📜 POLICY
    try:
        engine.validate(text)
    except Exception as e:
        decision["decision"] = "BLOCK"
        decision["violations"].append(str(e))

    # ⚠️ RISK
    risk_score = calculate_risk(text)
    decision["risk_score"] = risk_score

    if risk_score > 0.8 and decision["decision"] != "BLOCK":
        decision["decision"] = "REVIEW"

    # 📊 AUDIT
    log_event(user_id, f"decision:{decision['decision']}")

    return decision
