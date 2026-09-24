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


def test_platform_host_is_accepted() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health", headers={"host": "sporty.fastapicloud.dev"})

    assert response.status_code == 200


class FailingRateLimiter:
    async def check(self, key: str):
        raise RuntimeError("redis unavailable")


def test_rate_limit_fails_closed_when_enabled(monkeypatch) -> None:
    from app import main

    monkeypatch.setattr(main, "rate_limiter", FailingRateLimiter())
    monkeypatch.setattr(main.settings, "rate_limit_fail_closed", True)

    client = TestClient(main.app)
    response = client.get("/api/v1/meta", headers={"host": "localhost"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "rate_limit_unavailable"
