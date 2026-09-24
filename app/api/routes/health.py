from fastapi import APIRouter

from app.cache import check_redis
from app.db import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    database_ready = check_database()
    redis_ready = await check_redis()

    if not database_ready or not redis_ready:
        return {"status": "not_ready"}

    return {"status": "ready"}
