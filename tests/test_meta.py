from fastapi.testclient import TestClient

from app.main import app


def test_meta_exposes_frontend_markets_and_strategies() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    body = response.json()
    assert body["app_name"] == "Sporty"
    assert {item["id"] for item in body["markets"]} == {
        "over_1_5",
        "over_2_5",
        "btts",
        "under_2_5",
        "under_4_5",
    }
    assert {item["id"] for item in body["strategies"]} == {
        "1k",
        "5k_random",
        "weekly_safe",
    }


def test_request_id_can_be_provided_by_frontend() -> None:
    client = TestClient(app)
    request_id = "frontend-test-123"

    response = client.get("/api/v1/meta", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
