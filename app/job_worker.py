from __future__ import annotations

import asyncio
import json
import logging
import time

import logfire

from app.cache import get_redis
from app.db import SessionLocal
from app.job_executor import execute_prediction_job
from app.jobs import MAX_RETRIES, QUEUE_KEY, JobStatus, PredictionJobModel, utcnow
from app.metrics import JOB_COMPLETED, JOB_DURATION, JOB_FAILED, JOB_RETRIES

logger = logging.getLogger(__name__)


async def process_job(job_id: str) -> None:
    redis = get_redis()
    lock_key = f"job-lock:{job_id}"
    if not await redis.set(lock_key, "1", nx=True, ex=3600):
        return

    try:
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

        started = time.perf_counter()
        with logfire.span("prediction_job", job_id=job_id, job_type=job_type):
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
                    should_retry = job.retry_count < MAX_RETRIES
                    if should_retry:
                        job.status = JobStatus.QUEUED
                    else:
                        job.status = JobStatus.FAILED
                        job.completed_at = utcnow()
                    db.commit()

                JOB_RETRIES.add(1)
                JOB_DURATION.record(time.perf_counter() - started)

                if should_retry:
                    logfire.warning(
                        "Prediction job failed and will be retried",
                        job_id=job_id,
                        job_type=job_type,
                        retry_count=job.retry_count,
                    )
                    await asyncio.sleep(min(2 ** job.retry_count, 10))
                    await redis.rpush(
                        QUEUE_KEY,
                        json.dumps({"job_id": job_id}, separators=(",", ":")),
                    )
                else:
                    JOB_FAILED.add(1)
                    logfire.error(
                        "Prediction job failed permanently",
                        job_id=job_id,
                        job_type=job_type,
                        retry_count=job.retry_count,
                    )
                return

        JOB_DURATION.record(time.perf_counter() - started)
        JOB_COMPLETED.add(1)
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
    finally:
        await redis.delete(lock_key)


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
