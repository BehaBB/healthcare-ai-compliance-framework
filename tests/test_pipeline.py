from tooling.pipeline import process_request


def test_block():
    res = process_request("u1", "SSN 123-45-6789")
    assert res["decision"] == "BLOCK"


def test_allow():
    res = process_request("u1", "Hello")
    assert res["decision"] == "ALLOW"

def test_security_block():
    # если сделаешь check_security False
    pass


def test_review_path():
    # риск > 0.8
    pass
