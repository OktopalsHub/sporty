from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import health


def test_ready_when_database_is_available(monkeypatch) -> None:
    monkeypatch.setattr(health, "check_database", lambda: True)

    response = TestClient(app).get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(health, "check_database", lambda: False)

    response = TestClient(app).get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "not_ready"}
