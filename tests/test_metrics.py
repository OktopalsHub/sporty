from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_is_public():
    response = TestClient(app).get("/api/v1/metrics")
    assert response.status_code == 200
    assert "sporty_http_requests_total" in response.text
