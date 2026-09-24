from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_api_key_is_not_required_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "api_key", None)

    response = TestClient(app).get("/api/v1/meta")

    assert response.status_code == 200


def test_api_key_protects_api_routes(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "api_key", "test-secret")

    client = TestClient(app)

    unauthorized = client.get("/api/v1/meta")
    authorized = client.get("/api/v1/meta", headers={"X-API-Key": "test-secret"})
    invalid = client.get("/api/v1/meta", headers={"X-API-Key": "wrong"})

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "invalid_api_key"
    assert authorized.status_code == 200
    assert invalid.status_code == 401


def test_health_and_readiness_remain_public(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "api_key", "test-secret")

    client = TestClient(app)

    health_response = client.get("/api/v1/health")
    ready_response = client.get("/api/v1/ready")

    assert health_response.status_code == 200
    assert ready_response.status_code in {200, 503}
