from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_retry_and_delete_require_authentication() -> None:
    document_id = uuid4()
    with TestClient(app) as client:
        assert client.post(f"/documents/{document_id}/retry").status_code == 401
        assert client.delete(f"/documents/{document_id}").status_code == 401
