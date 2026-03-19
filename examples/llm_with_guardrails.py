from tooling.policy_engine import PolicyEngine, no_phi_rule

engine = PolicyEngine()
engine.add_rule(no_phi_rule)

def run(input_data):
    engine.validate(input_data)
    return "LLM response"
