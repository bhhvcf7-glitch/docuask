import json

from fastapi.testclient import TestClient

from app.main import app


def test_request_log_is_json_and_includes_request_id(capsys) -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    records = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if '"event": "http_request"' in line
    ]
    assert response.status_code == 200
    assert len(records) == 1
    assert records[0]["method"] == "GET"
    assert records[0]["status_code"] == 200
    assert records[0]["request_id"] == response.headers["X-Request-ID"]
    assert len(records[0]["request_id"]) == 32
