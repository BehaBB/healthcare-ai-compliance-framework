from tooling.policy_engine import no_phi_rule

def test_safe():
    assert no_phi_rule("hello") == True

def test_block():
    assert no_phi_rule("SSN: 123") == False
