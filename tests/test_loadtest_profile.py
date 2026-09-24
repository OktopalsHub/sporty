from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_loadtest_profile_exists() -> None:
    profile = ROOT / "loadtest" / "locustfile.py"
    assert profile.exists()
    content = profile.read_text()
    assert "HttpUser" in content
    assert "/api/v1/health" in content
    assert "/api/v1/ready" in content


def test_loadtest_profile_does_not_create_prediction_jobs() -> None:
    content = (ROOT / "loadtest" / "locustfile.py").read_text()
    assert "/api/v1/jobs" not in content
    assert "/generate" not in content
