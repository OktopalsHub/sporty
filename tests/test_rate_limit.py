import pytest

from app.rate_limit import RedisRateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, 1)


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_until_limit() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis, limit=2, window_seconds=60)

    first = await limiter.check("client")
    second = await limiter.check("client")

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert redis.ttls["rate-limit:client"] == 60


@pytest.mark.asyncio
async def test_rate_limiter_blocks_requests_over_limit() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis, limit=1, window_seconds=60)

    await limiter.check("client")
    blocked = await limiter.check("client")

    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after == 60
