from fastapi.testclient import TestClient

from app.api.dependencies import get_resources
from app.api.routes import health as health_routes
from app.main import app


def test_health_is_liveness_only() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_readiness_returns_503_when_dependencies_fail(monkeypatch) -> None:
    async def not_available(resources):
        raise OSError("database unavailable")

    monkeypatch.setattr(health_routes, "check_dependencies", not_available)
    app.dependency_overrides[get_resources] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["detail"] == "Dependencies are not ready"


def test_readiness_reports_ok_when_both_dependencies_work(monkeypatch) -> None:
    async def working(resources):
        return None

    monkeypatch.setattr(health_routes, "check_dependencies", working)
    app.dependency_overrides[get_resources] = lambda: object()
    try:
        with TestClient(app) as client:
            assert client.get("/ready").json() == {"status": "ok"}
    finally:
        app.dependency_overrides.clear()
