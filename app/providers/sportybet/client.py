from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.domain.provider import ProviderEvent, ProviderMarket, ProviderOutcome


class SportyBetError(RuntimeError):
    """Provider-level error raised by the SportyBet adapter."""


class SportyBetClient:
    """Thin adapter over SportyBet's web API.

    Provider-specific HTTP paths and response shapes stay inside this class.
    SportyBet does not expose a stable public developer API, so this boundary
    makes future endpoint changes isolated from the prediction engine.
    """

    def __init__(
        self,
        base_url: str = "https://www.sportybet.com",
        region: str = "ng",
        timeout: float = 15.0,
        min_interval: float = 0.25,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.region = region.lower()
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        async with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Current-Country": self.region.upper(),
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
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue

                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("bizCode") not in (None, 10000):
                        raise SportyBetError(
                            f"SportyBet returned bizCode={payload.get('bizCode')}"
                        )
                    return payload
                except (httpx.HTTPError, ValueError, SportyBetError) as exc:
                    last_error = exc
                    if attempt < self.max_retries and not isinstance(exc, SportyBetError):
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    break

            raise SportyBetError("SportyBet request failed") from last_error

    async def get_upcoming_events(
        self,
        *,
        page: int = 1,
        page_size: int = 100,
        hours: int = 168,
        market_ids: str | None = None,
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

    async def get_event_markets(self, event_id: str) -> ProviderEvent:
        events, _ = await self.get_upcoming_events(page=1, page_size=100)
        for event in events:
            if event.id == event_id:
                return event
        raise SportyBetError(f"Event {event_id} was not found in the current feed")

    async def create_booking(self, selections: list[dict[str, str | None]]) -> dict[str, Any]:
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
        return await self._request("POST", f"/api/{self.region}/orders/share", json=payload)

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
