from __future__ import annotations

import asyncio
from redis.asyncio import Redis

from app.config import get_settings


_redis: Redis | None = None
_redis_loop: asyncio.AbstractEventLoop | None = None


def get_redis() -> Redis:
    global _redis, _redis_loop

    settings = get_settings()
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _redis is None or (
        current_loop is not None and current_loop is not _redis_loop
    ):
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_timeout,
            socket_timeout=settings.redis_timeout,
            socket_keepalive=True,
            max_connections=settings.redis_max_connections,
            health_check_interval=settings.redis_health_check_interval,
        )
        _redis_loop = current_loop

    return _redis


async def check_redis() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def close_redis() -> None:
    global _redis, _redis_loop

    if _redis is not None:
        await _redis.aclose()
    _redis = None
    _redis_loop = None



def _clear_redis_cache() -> None:
    global _redis, _redis_loop
    _redis = None
    _redis_loop = None


get_redis.cache_clear = _clear_redis_cache
