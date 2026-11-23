from fastapi.testclient import TestClient

from app.main import app


def test_qa_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post("/qa/ask", json={"question": "What is in the PDF?"})
    assert response.status_code == 401
