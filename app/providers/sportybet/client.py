from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.config import get_settings
from app.domain.provider import ProviderEvent, ProviderMarket, ProviderOutcome

logger = logging.getLogger(__name__)


class SportyBetError(RuntimeError):
    """Provider-level error raised by the SportyBet adapter."""


_CONFIG_MARKERS = (
    "PARSE_API_KEY is required",
    "provider is not configured",
    "not configured",
)


def is_configuration_error(exc: BaseException) -> bool:
    message = str(exc)
    return any(marker in message for marker in _CONFIG_MARKERS)


def provider_http_status(exc: BaseException) -> int:
    """Map a provider failure to an API status code.

    Configuration problems (missing Parse key) are 503 with an actionable
    message. Genuine upstream outages stay 502 so clients can retry.
    """
    if is_configuration_error(exc):
        return 503
    return 502


def provider_http_detail(exc: BaseException) -> str:
    if is_configuration_error(exc):
        return (
            "Prediction provider is not configured. "
            "Set SPORTYBET_PROVIDER=direct for keyless local development, "
            "or configure PARSE_API_KEY when SPORTYBET_PROVIDER=parse. "
            f"Provider error: {exc}"
        )
    detail = str(exc) or "SportyBet request failed"
    return (
        f"{detail} "
        "(provider temporarily unavailable - retry, reduce page_size/hours, "
        "or submit a background job via POST /api/v1/jobs)"
    )


# Short-lived in-process cache of the last successful feed. When both
# providers fail, generators can serve this stale feed instead of 502ing
# every request during a transient upstream outage.
_FEED_CACHE: dict[tuple[Any, ...], tuple[list[ProviderEvent], int, float]] = {}
_FEED_CACHE_TTL_SECONDS = 300.0
_FEED_STALE_SECONDS = 1800.0


def _cache_key(
    page: int, page_size: int, hours: int, market_ids: str | None
) -> tuple[Any, ...]:
    return ("upcoming", page, page_size, hours, market_ids)


def _cache_get(
    key: tuple[Any, ...],
) -> tuple[list[ProviderEvent], int] | None:
    entry = _FEED_CACHE.get(key)
    if entry is None:
        return None
    events, total, stored_at = entry
    if time.monotonic() - stored_at > _FEED_STALE_SECONDS:
        _FEED_CACHE.pop(key, None)
        return None
    return events, total


def _cache_put(
    key: tuple[Any, ...], events: list[ProviderEvent], total: int
) -> None:
    _FEED_CACHE[key] = (events, total, time.monotonic())


def clear_feed_cache() -> None:
    _FEED_CACHE.clear()


class SportyBetClient:
    """Thin adapter over SportyBet's web API.

    Provider-specific HTTP paths and response shapes stay inside this class.
    SportyBet does not expose a stable public developer API, so this boundary
    makes future endpoint changes isolated from the prediction engine.

    The client tries the configured provider first (``direct`` by default,
    ``parse`` when ``SPORTYBET_PROVIDER=parse``) and automatically falls back
    to the other provider on failure. A missing Parse key therefore degrades
    to the keyless direct feed instead of 502ing every generation request.
    """

    def __init__(
        self,
        base_url: str | None = None,
        region: str | None = None,
        timeout: float | None = None,
        min_interval: float | None = None,
        max_retries: int | None = None,
        provider: str | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.sportybet_base_url).rstrip("/")
        self.region = (region or settings.sportybet_region).lower()
        self.timeout = timeout if timeout is not None else settings.sportybet_timeout
        self.min_interval = (
            min_interval if min_interval is not None else settings.sportybet_min_interval
        )
        self.max_retries = (
            max_retries if max_retries is not None else settings.sportybet_max_retries
        )
        self.provider = (provider or settings.sportybet_provider or "direct").lower()
        self._parse_client = None
        try:
            from app.providers.sportybet.parse_client import ParseSportyBetClient

            self._parse_client = ParseSportyBetClient()
        except Exception:  # pragma: no cover - import-time safety
            logger.warning("Parse SportyBet adapter unavailable", exc_info=True)
            self._parse_client = None
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    def _provider_order(self) -> list[str]:
        if self.provider == "parse":
            return ["parse", "direct"]
        return ["direct", "parse"]

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        async with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Current-Country": self.region.upper(),
                # SportyBet's web API rejects bare non-browser clients.
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "Referer": f"{self.base_url}/",
                "Origin": self.base_url,
            }
            headers.update(kwargs.pop("headers", {}))

            last_error: Exception | None = None
            for attempt in range(self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.request(
                            method,
                            f"{self.base_url}{path}",
                            headers=headers,
                            **kwargs,
                        )
                    self._last_request = time.monotonic()

                    if response.status_code == 429 or response.status_code >= 500:
                        last_error = httpx.HTTPStatusError(
                            f"SportyBet returned HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue
                        break

                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("bizCode") not in (None, 10000):
                        raise SportyBetError(
                            f"SportyBet returned bizCode={payload.get('bizCode')}"
                        )
                    return payload
                except SportyBetError as exc:
                    last_error = exc
                    break
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    break

            detail = f": {last_error}" if last_error else ""
            raise SportyBetError(f"SportyBet request failed{detail}") from last_error

    async def get_upcoming_events(
        self,
        *,
        page: int = 1,
        page_size: int = 100,
        hours: int = 168,
        market_ids: str | None = None,
    ) -> tuple[list[ProviderEvent], int]:
        key = _cache_key(page, page_size, hours, market_ids)
        errors: list[str] = []
        for name in self._provider_order():
            try:
                if name == "parse":
                    events, total = await self._fetch_via_parse(
                        page=page,
                        page_size=page_size,
                        hours=hours,
                        market_ids=market_ids,
                    )
                else:
                    events, total = await self._fetch_direct(
                        page=page,
                        page_size=page_size,
                        hours=hours,
                        market_ids=market_ids,
                    )
            except SportyBetError as exc:
                errors.append(f"{name}: {exc}")
                logger.warning("SportyBet %s feed failed: %s", name, exc)
                continue
            _cache_put(key, events, total)
            return events, total

        cached = _cache_get(key)
        if cached is not None:
            logger.warning(
                "Serving stale SportyBet feed for %s (failures: %s)", key, errors
            )
            return cached

        raise SportyBetError(
            "SportyBet feed unavailable (tried "
            + ", ".join(self._provider_order())
            + "). "
            + "; ".join(errors)
        )

    async def _fetch_direct(
        self,
        *,
        page: int,
        page_size: int,
        hours: int,
        market_ids: str | None,
    ) -> tuple[list[ProviderEvent], int]:
        params: dict[str, Any] = {
            "sportId": "sr:sport:1",
            "pageNum": page,
            "pageSize": min(page_size, 100),
            "todayGames": "false",
            "timeline": hours,
            "_t": int(time.time() * 1000),
        }
        if market_ids:
            params["marketId"] = market_ids

        payload = await self._request(
            "GET",
            f"/api/{self.region}/factsCenter/pcUpcomingEvents",
            params=params,
        )
        data = payload.get("data") or {}
        tournaments = data.get("tournaments") or []

        events: list[ProviderEvent] = []
        for tournament in tournaments:
            for raw in tournament.get("events") or []:
                events.append(self._normalize_event(raw, tournament))

        return events, int(data.get("totalNum") or len(events))

    async def _fetch_via_parse(
        self,
        *,
        page: int,
        page_size: int,
        hours: int,
        market_ids: str | None,
    ) -> tuple[list[ProviderEvent], int]:
        if self._parse_client is None:
            raise SportyBetError("Parse provider is not configured")
        return await self._parse_client.get_upcoming_events(
            page=page,
            page_size=page_size,
            hours=hours,
            market_ids=market_ids,
        )

    async def get_event_markets(self, event_id: str) -> ProviderEvent:
        errors: list[str] = []
        for name in self._provider_order():
            try:
                if name == "parse":
                    if self._parse_client is None:
                        raise SportyBetError("Parse provider is not configured")
                    return await self._parse_client.get_event_markets(event_id)
                events, _ = await self._fetch_direct(page=1, page_size=100, hours=168, market_ids=None)
                for event in events:
                    if event.id == event_id:
                        return event
                raise SportyBetError(
                    f"Event {event_id} was not found in the current feed"
                )
            except SportyBetError as exc:
                # A definitive "not found" from one feed is still worth
                # checking against the fallback feed before giving up.
                if "was not found" in str(exc) and name != self._provider_order()[-1]:
                    errors.append(f"{name}: {exc}")
                    continue
                if "was not found" in str(exc):
                    raise
                errors.append(f"{name}: {exc}")
                logger.warning("SportyBet %s event lookup failed: %s", name, exc)
                continue
        raise SportyBetError(
            f"Event {event_id} was not found in the current feed "
            f"({' ; '.join(errors)})"
        )

    async def create_booking(self, selections: list[dict[str, str | None]]) -> dict[str, Any]:
        errors: list[str] = []
        for name in self._provider_order():
            try:
                if name == "parse":
                    if self._parse_client is None:
                        raise SportyBetError("Parse provider is not configured")
                    return await self._parse_client.create_booking(selections)
                payload = {
                    "selections": [
                        {
                            "eventId": item["event_id"],
                            "marketId": item["market_id"],
                            "specifier": item.get("specifier"),
                            "outcomeId": item["outcome_id"],
                        }
                        for item in selections
                    ]
                }
                return await self._request(
                    "POST", f"/api/{self.region}/orders/share", json=payload
                )
            except SportyBetError as exc:
                errors.append(f"{name}: {exc}")
                logger.warning("SportyBet %s booking failed: %s", name, exc)
                continue
        raise SportyBetError("SportyBet booking failed: " + "; ".join(errors))

    @staticmethod
    def _normalize_event(
        raw: dict[str, Any],
        tournament: dict[str, Any],
    ) -> ProviderEvent:
        start_ms = int(raw.get("estimateStartTime") or 0)
        start_time = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)

        markets: list[ProviderMarket] = []
        for market in raw.get("markets") or []:
            outcomes = tuple(
                ProviderOutcome(
                    id=str(outcome.get("id")),
                    description=str(outcome.get("desc") or ""),
                    odds=Decimal(str(outcome.get("odds"))),
                    active=bool(outcome.get("isActive", True)),
                )
                for outcome in market.get("outcomes") or []
                if outcome.get("id") is not None and outcome.get("odds") is not None
            )
            markets.append(
                ProviderMarket(
                    id=str(market.get("id")),
                    description=str(market.get("desc") or ""),
                    specifier=market.get("specifier"),
                    active=str(market.get("status", "")).lower()
                    not in {"closed", "suspended"},
                    outcomes=outcomes,
                )
            )

        return ProviderEvent(
            id=str(raw.get("eventId")),
            tournament_id=(
                str(tournament.get("id")) if tournament.get("id") is not None else None
            ),
            tournament_name=tournament.get("name"),
            home_team=str(raw.get("homeTeamName") or ""),
            away_team=str(raw.get("awayTeamName") or ""),
            start_time=start_time,
            status=str(raw.get("matchStatus") or ""),
            markets=tuple(markets),
        )
