import pytest

from app.cache import check_redis


class FakeRedis:
    async def ping(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_check_redis_reports_healthy(monkeypatch) -> None:
    monkeypatch.setattr("app.cache.get_redis", lambda: FakeRedis())

    assert await check_redis() is True


@pytest.mark.asyncio
async def test_check_redis_reports_unhealthy(monkeypatch) -> None:
    class BrokenRedis:
        async def ping(self) -> bool:
            raise RuntimeError("redis unavailable")

    monkeypatch.setattr("app.cache.get_redis", lambda: BrokenRedis())

    assert await check_redis() is False
