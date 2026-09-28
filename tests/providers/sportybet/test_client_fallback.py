from unittest.mock import AsyncMock, patch

import pytest

from app.providers.sportybet.client import (
    SportyBetClient,
    SportyBetError,
    clear_feed_cache,
    provider_http_detail,
    provider_http_status,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_feed_cache()
    yield
    clear_feed_cache()


async def test_parse_missing_key_falls_back_to_direct():
    client = SportyBetClient(provider="parse")
    with (
        patch.object(
            SportyBetClient,
            "_fetch_via_parse",
            new=AsyncMock(
                side_effect=SportyBetError("PARSE_API_KEY is required when SPORTYBET_PROVIDER=parse")
            ),
        ),
        patch.object(
            SportyBetClient, "_fetch_direct", new=AsyncMock(return_value=(["evt"], 1))
        ),
    ):
        events, total = await client.get_upcoming_events(page=1, page_size=25, hours=24)
    assert events == ["evt"]
    assert total == 1


async def test_stale_feed_served_when_both_providers_fail():
    client = SportyBetClient(provider="direct")
    with (
        patch.object(
            SportyBetClient, "_fetch_direct", new=AsyncMock(side_effect=SportyBetError("down"))
        ),
        patch.object(
            SportyBetClient, "_fetch_via_parse", new=AsyncMock(return_value=(["evt"], 1))
        ),
    ):
        await client.get_upcoming_events(page=2, page_size=25, hours=24)
    with (
        patch.object(
            SportyBetClient, "_fetch_direct", new=AsyncMock(side_effect=SportyBetError("down"))
        ),
        patch.object(
            SportyBetClient, "_fetch_via_parse", new=AsyncMock(side_effect=SportyBetError("down"))
        ),
    ):
        events, _ = await client.get_upcoming_events(page=2, page_size=25, hours=24)
    assert events == ["evt"]


def test_configuration_error_maps_to_503():
    exc = SportyBetError("PARSE_API_KEY is required when SPORTYBET_PROVIDER=parse")
    assert provider_http_status(exc) == 503
    assert "SPORTYBET_PROVIDER=direct" in provider_http_detail(exc)


def test_upstream_error_maps_to_502_with_retry_hint():
    exc = SportyBetError("SportyBet request failed: 500")
    assert provider_http_status(exc) == 502
    assert "retry" in provider_http_detail(exc).lower()
