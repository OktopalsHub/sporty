from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.config import get_settings
from app.domain.provider import ProviderEvent, ProviderMarket, ProviderOutcome
from app.providers.sportybet.client import SportyBetError


class ParseSportyBetClient:
    """Adapter for the maintained Parse SportyBet Nigeria API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        min_interval: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.parse_api_key
        self.base_url = (
            base_url or settings.parse_api_base_url
        ).rstrip("/")
        self.timeout = (
            timeout if timeout is not None else settings.sportybet_timeout
        )
        self.min_interval = (
            min_interval
            if min_interval is not None
            else settings.sportybet_min_interval
        )
        self.max_retries = (
            max_retries
            if max_retries is not None
            else settings.sportybet_max_retries
        )
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise SportyBetError(
                "PARSE_API_KEY is required when SPORTYBET_PROVIDER=parse"
            )

        async with self._lock:
            wait = self.min_interval - (
                time.monotonic() - self._last_request
            )
            if wait > 0:
                await asyncio.sleep(wait)

            last_error: Exception | None = None
            for attempt in range(self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(
                        timeout=self.timeout
                    ) as client:
                        response = await client.request(
                            method,
                            f"{self.base_url}/{endpoint}",
                            headers={
                                "Accept": "application/json",
                                "Content-Type": "application/json",
                                "X-API-Key": self.api_key,
                            },
                            **kwargs,
                        )
                    self._last_request = time.monotonic()

                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue

                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise SportyBetError(
                            "Parse provider returned invalid JSON"
                        )
                    if payload.get("status") == "error":
                        raise SportyBetError(
                            str(
                                payload.get("message")
                                or "Parse provider returned an error"
                            )
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

            raise SportyBetError(
                "Parse SportyBet request failed: "
                f"{last_error or 'unknown error'}"
            ) from last_error

    async def get_upcoming_events(
        self,
        *,
        page: int = 1,
        page_size: int = 100,
        hours: int = 168,
        market_ids: str | None = None,
    ) -> tuple[list[ProviderEvent], int]:
        params: dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 100),
            "hours": hours,
        }
        if market_ids:
            params["market"] = market_ids

        payload = await self._request(
            "GET",
            "get_prematch_football_markets",
            params=params,
        )
        data = payload.get("data") or payload
        return self._normalize_outcomes(data.get("outcomes") or [])

    async def get_event_markets(self, event_id: str) -> ProviderEvent:
        payload = await self._request(
            "GET",
            "get_football_event_markets",
            params={"event_id": event_id},
        )
        data = payload.get("data") or payload
        events, _ = self._normalize_outcomes(data.get("outcomes") or [])
        if not events:
            raise SportyBetError(
                f"Event {event_id} was not found"
            )
        return events[0]

    async def create_booking(
        self,
        selections: list[dict[str, str | None]],
    ) -> dict[str, Any]:
        payload = {
            "selections": json.dumps(
                [
                    {
                        "eventId": item["event_id"],
                        "marketId": item["market_id"],
                        **(
                            {"specifier": item["specifier"]}
                            if item.get("specifier")
                            else {}
                        ),
                        "outcomeId": item["outcome_id"],
                    }
                    for item in selections
                ]
            )
        }
        return await self._request(
            "POST",
            "book_bet",
            json=payload,
        )

    @staticmethod
    def _normalize_outcomes(
        outcomes: list[dict[str, Any]],
    ) -> tuple[list[ProviderEvent], int]:
        grouped: dict[str, dict[str, Any]] = {}

        for raw in outcomes:
            event_id = raw.get("eventId")
            if event_id is None:
                continue

            event_id = str(event_id)
            event = grouped.setdefault(
                event_id,
                {
                    "tournament_id": raw.get("tournamentId"),
                    "tournament_name": raw.get("tournament"),
                    "home_team": str(raw.get("homeTeamName") or ""),
                    "away_team": str(raw.get("awayTeamName") or ""),
                    "start_time": ParseSportyBetClient._parse_time(
                        raw.get("estimateStartTime")
                        or raw.get("kickoffTime")
                    ),
                    "status": str(raw.get("matchStatus") or "Not start"),
                    "markets": {},
                },
            )

            market_id = raw.get("marketId")
            outcome_id = raw.get("outcomeId")
            if (
                market_id is None
                or outcome_id is None
                or raw.get("odds") is None
            ):
                continue

            specifier = raw.get("specifier")
            market_key = (
                str(market_id),
                str(specifier) if specifier is not None else None,
            )
            market = event["markets"].setdefault(
                market_key,
                {
                    "description": str(raw.get("marketDesc") or ""),
                    "outcomes": [],
                },
            )
            market["outcomes"].append(
                ProviderOutcome(
                    id=str(outcome_id),
                    description=str(raw.get("outcomeDesc") or ""),
                    odds=Decimal(str(raw["odds"])),
                    active=True,
                )
            )

        events: list[ProviderEvent] = []
        for event_id, raw_event in grouped.items():
            markets = tuple(
                ProviderMarket(
                    id=market_id,
                    description=data["description"],
                    specifier=specifier,
                    active=(
                        str(raw_event["status"]).lower()
                        not in {
                            "closed",
                            "finished",
                            "cancelled",
                            "suspended",
                        }
                    ),
                    outcomes=tuple(data["outcomes"]),
                )
                for (market_id, specifier), data
                in raw_event["markets"].items()
            )
            events.append(
                ProviderEvent(
                    id=event_id,
                    tournament_id=(
                        str(raw_event["tournament_id"])
                        if raw_event["tournament_id"] is not None
                        else None
                    ),
                    tournament_name=raw_event["tournament_name"],
                    home_team=raw_event["home_team"],
                    away_team=raw_event["away_team"],
                    start_time=raw_event["start_time"],
                    status=raw_event["status"],
                    markets=markets,
                )
            )

        events.sort(key=lambda item: item.start_time)
        return events, len(events)

    @staticmethod
    def _parse_time(value: Any) -> datetime:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc,
            )

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        return datetime.fromtimestamp(0, tz=timezone.utc)
