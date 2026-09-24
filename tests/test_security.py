from fastapi.testclient import TestClient

from app.main import app


def test_security_headers_are_present() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health", headers={"host": "localhost"})

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


def test_unknown_host_is_rejected() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health", headers={"host": "attacker.example"})

    assert response.status_code == 400

