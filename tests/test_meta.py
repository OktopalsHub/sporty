from fastapi.testclient import TestClient

from app.domain.markets import Market
from app.main import app


def test_meta_exposes_frontend_markets_and_strategies() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    body = response.json()
    assert body["app_name"] == "Sporty"
    assert {item["id"] for item in body["markets"]} == {market.value for market in Market}
    assert {item["id"] for item in body["strategies"]} == {
        "custom",
    }


def test_request_id_can_be_provided_by_frontend() -> None:
    client = TestClient(app)
    request_id = "frontend-test-123"

    response = client.get("/api/v1/meta", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
