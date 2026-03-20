from tooling.policy_engine import no_phi_rule

def test_safe_basic():
    assert no_phi_rule("hello world") is True


def test_block_ssn():
    assert no_phi_rule("SSN: 123-45-6789") is False


def test_block_medical_record():
    assert no_phi_rule("Patient medical record #12345") is False


def test_block_phone():
    assert no_phi_rule("Call me at 555-123-4567") is False


def test_block_email():
    assert no_phi_rule("email: test@example.com") is False


def test_case_insensitive():
    assert no_phi_rule("ssn: 123") is False


def test_empty_input():
    assert no_phi_rule("") is True


def test_mixed_safe_text():
    assert no_phi_rule("Hello, how are you today?") is True
