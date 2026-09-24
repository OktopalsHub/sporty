from fastapi import APIRouter

from app.db import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    if not check_database():
        return {"status": "not_ready"}
    return {"status": "ready"}
