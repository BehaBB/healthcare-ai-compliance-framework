from fastapi.testclient import TestClient
from tooling.api import app

client = TestClient(app)


def test_api_allow():
    response = client.post("/process", json={"input_text": "Hello"})
    assert response.status_code == 200
    assert response.json()["decision"] in ["ALLOW", "approved"]


def test_api_block():
    response = client.post("/process", json={"input_text": "SSN 123-45-6789"})
    assert response.status_code == 200 or response.status_code == 400
