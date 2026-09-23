from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class RedisRateLimiter:
    def __init__(self, redis: Redis, limit: int, window_seconds: int) -> None:
        self.redis = redis
        self.limit = limit
        self.window_seconds = window_seconds

    async def check(self, key: str) -> RateLimitResult:
        bucket = f"rate-limit:{key}"
        count = await self.redis.incr(bucket)

        if count == 1:
            await self.redis.expire(bucket, self.window_seconds)

        remaining = max(self.limit - count, 0)
        if count <= self.limit:
            return RateLimitResult(
                allowed=True,
                limit=self.limit,
                remaining=remaining,
                retry_after=0,
            )

        ttl = await self.redis.ttl(bucket)
        return RateLimitResult(
            allowed=False,
            limit=self.limit,
            remaining=0,
            retry_after=max(ttl, 1),
        )
