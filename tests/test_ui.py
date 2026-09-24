from fastapi.testclient import TestClient

from app.main import app


def test_root_serves_main_ui() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Build your SportyBet ticket" in response.text
