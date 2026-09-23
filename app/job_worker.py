from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select

from app.cache import get_redis
from app.db import SessionLocal
from app.job_executor import execute_prediction_job
from app.jobs import (
    MAX_RETRIES,
    QUEUE_KEY,
    JobStatus,
    PredictionJobModel,
    utcnow,
)

logger = logging.getLogger(__name__)


async def process_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(PredictionJobModel, job_id)
        if job is None or job.status == JobStatus.COMPLETED:
            return
        job.status = JobStatus.RUNNING
        job.started_at = utcnow()
        job.progress = 10
        db.commit()
        job_type = job.job_type
        payload = dict(job.payload)

    try:
        result = await execute_prediction_job(job_type, payload)
    except Exception as exc:
        with SessionLocal() as db:
            job = db.get(PredictionJobModel, job_id)
            if job is None:
                return
            job.retry_count += 1
            job.error = str(exc)
            job.progress = 0
            if job.retry_count < MAX_RETRIES:
                job.status = JobStatus.QUEUED
            else:
                job.status = JobStatus.FAILED
                job.completed_at = utcnow()
            db.commit()

        if job.retry_count < MAX_RETRIES:
            await get_redis().rpush(
                QUEUE_KEY,
                json.dumps({"job_id": job_id}, separators=(",", ":")),
            )
        return

    with SessionLocal() as db:
        job = db.get(PredictionJobModel, job_id)
        if job is None:
            return
        job.result = result
        job.error = None
        job.progress = 100
        job.status = JobStatus.COMPLETED
        job.completed_at = utcnow()
        db.commit()


async def run_worker() -> None:
    redis = get_redis()
    logger.info("Prediction worker started")
    while True:
        item = await redis.blpop(QUEUE_KEY, timeout=5)
        if not item:
            continue
        _, raw_job = item
        try:
            message = json.loads(raw_job)
            await process_job(message["job_id"])
        except Exception:
            logger.exception("Failed to process queued job")


if __name__ == "__main__":
    asyncio.run(run_worker())
