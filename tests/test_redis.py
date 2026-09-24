import pytest

from app.cache import check_redis, get_redis


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


def test_redis_client_uses_managed_redis_compatible_options(monkeypatch) -> None:
    class FakeSettings:
        redis_url = "rediss://default:secret@example.upstash.io:6379"
        redis_timeout = 2.5
        redis_max_connections = 7
        redis_health_check_interval = 45

    monkeypatch.setattr("app.cache.get_settings", lambda: FakeSettings())

    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("app.cache.Redis", type("RedisFactory", (), {
        "from_url": staticmethod(lambda url, **kwargs: captured.update(url=url, **kwargs) or FakeClient())
    }))

    get_redis.cache_clear()
    client = get_redis()

    assert client is not None
    assert captured["url"].startswith("rediss://")
    assert captured["socket_connect_timeout"] == 2.5
    assert captured["socket_timeout"] == 2.5
    assert captured["socket_keepalive"] is True
    assert captured["max_connections"] == 7
    assert captured["health_check_interval"] == 45
    get_redis.cache_clear()
