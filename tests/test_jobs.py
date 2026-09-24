from datetime import datetime, timezone

from app.jobs import PredictionJobModel, JobStatus


def test_job_model_defaults():
    job = PredictionJobModel(
        id="job-1",
        job_type="1k",
        status=JobStatus.QUEUED,
        progress=0,
        payload={"page": 1},
        created_at=datetime.now(timezone.utc),
    )
    assert job.status == JobStatus.QUEUED
    assert job.retry_count == 0
    assert job.progress == 0
