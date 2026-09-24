from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.job_executor import SUPPORTED_JOB_TYPES
from app.jobs import create_job, enqueue_job, get_job, serialize_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    job_type: str = Field(min_length=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=100)
    hours: int = Field(default=168, ge=1, le=720)
    min_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_pool_size: int = Field(default=150, ge=1, le=1000)
    attempts: int = Field(default=25, ge=1, le=100)
    min_confidence: str = "high"
    min_days: int = Field(default=3, ge=1, le=7)
    candidate_limit_per_day: int = Field(default=40, ge=1, le=200)


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    progress: int
    result: dict | None
    error: str | None
    retry_count: int
    created_at: str
    started_at: str | None
    completed_at: str | None


@router.post("", response_model=JobResponse, status_code=202)
async def create_prediction_job(request: JobCreateRequest) -> JobResponse:
    if request.job_type not in SUPPORTED_JOB_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported job type. Use one of: {', '.join(sorted(SUPPORTED_JOB_TYPES))}",
        )
    job = create_job(request.job_type, request.model_dump(exclude={"job_type"}))
    await enqueue_job(job)
    return JobResponse(**await serialize_job(job))


@router.get("/{job_id}", response_model=JobResponse)
async def get_prediction_job(job_id: str) -> JobResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**await serialize_job(job))
