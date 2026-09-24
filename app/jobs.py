from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, SessionLocal
from app.cache import get_redis


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PredictionJobModel(Base):
    __tablename__ = "prediction_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


QUEUE_KEY = "jobs:prediction"
MAX_RETRIES = 3


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_job(job_type: str, payload: dict) -> PredictionJobModel:
    job = PredictionJobModel(
        id=str(uuid4()),
        job_type=job_type,
        status=JobStatus.QUEUED,
        progress=0,
        payload=payload,
        retry_count=0,
        created_at=utcnow(),
    )
    with SessionLocal() as db:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job


async def enqueue_job(job: PredictionJobModel) -> None:
    await get_redis().rpush(
        QUEUE_KEY,
        json.dumps({"job_id": job.id}, separators=(",", ":")),
    )


def get_job(job_id: str) -> PredictionJobModel | None:
    with SessionLocal() as db:
        return db.get(PredictionJobModel, job_id)


async def serialize_job(job: PredictionJobModel) -> dict:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
        "retry_count": job.retry_count,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
