from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_removed():
    response = TestClient(app).get("/api/v1/metrics")
    assert response.status_code == 404


def test_api_responses_keep_request_id():
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
