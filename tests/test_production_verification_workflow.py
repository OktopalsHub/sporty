from pathlib import Path

import yaml


def test_production_verification_workflow_is_manual_and_protected() -> None:
    workflow_path = Path(".github/workflows/production-verification.yml")
    workflow = yaml.safe_load(workflow_path.read_text())

    assert "workflow_dispatch" in workflow["on"]
    assert workflow["permissions"]["contents"] == "read"
    assert workflow["jobs"]["smoke"]["environment"] == "production"

    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert "base_url" in inputs
    assert "api_key" not in inputs

    steps = workflow["jobs"]["smoke"]["steps"]
    assert any(step.get("name") == "Check liveness" for step in steps)
    assert any(step.get("name") == "Check readiness" for step in steps)
    assert any(step.get("name") == "Check protected API" for step in steps)
    assert any(step.get("name") == "Check authenticated API" for step in steps)
