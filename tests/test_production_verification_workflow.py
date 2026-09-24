from pathlib import Path


def test_production_verification_workflow_is_manual_and_protected() -> None:
    content = Path(".github/workflows/production-verification.yml").read_text()

    assert "workflow_dispatch:" in content
    assert "permissions:" in content
    assert "contents: read" in content
    assert "environment: production" in content
    assert "base_url:" in content
    assert "api_key:" not in content
    assert "name: Check liveness" in content
    assert "name: Check readiness" in content
    assert "name: Check protected API" in content
    assert "name: Check authenticated API" in content
