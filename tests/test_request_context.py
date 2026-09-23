from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_request_id_is_generated() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_internal_errors_return_safe_error_response(monkeypatch) -> None:
    async def failing_handler(request, call_next):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(app, "user_middleware", [])
    app.middleware_stack = None
    app.middleware("http")(failing_handler)

    response = client.get("/api/v1/health")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal_server_error",
        "message": "Internal server error",
    }
    assert "secret internal detail" not in response.text
    assert response.headers["X-Request-ID"]
