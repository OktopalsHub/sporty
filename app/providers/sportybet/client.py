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
        base_url: str | None = None,
        region: str | None = None,
        timeout: float | None = None,
        min_interval: float | None = None,
        max_retries: int | None = None,
        provider: str | None = None,
        parse_api_key: str | None = None,
        parse_base_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = (provider or settings.sportybet_provider).lower().strip()
        self.base_url = (base_url or settings.sportybet_base_url).rstrip("/")
        self.region = (region or settings.sportybet_region).lower()
        self.timeout = timeout if timeout is not None else settings.sportybet_timeout
        self.min_interval = (
        self.max_retries = (
            max_retries if max_retries is not None else settings.sportybet_max_retries
        )
        )
        self.max_retries = max_retries if max_retries is not None else settings.sportybet_max_retries
        self.parse_api_key = parse_api_key or settings.parse_api_key
        self.parse_base_url = (parse_base_url or settings.parse_api_base_url).rstrip("/")
        if self.provider not in {"direct", "parse"}:
            raise ValueError("SPORTYBET_PROVIDER must be either 'direct' or 'parse'")
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self.provider == "parse":
            return await self._request_parse(method, path, **kwargs)
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
            raise SportyBetError(
                f"SportyBet request failed: {last_error or 'unknown error'}"
            ) from last_error
                        continue
                    break

            raise SportyBetError(f"SportyBet request failed: {last_error or 'unknown error'}") from last_error


    async def _request_parse(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        if not self.parse_api_key:
            raise SportyBetError("PARSE_API_KEY is required when SPORTYBET_PROVIDER=parse")
        async with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            last_error: Exception | None = None
                            headers={
                                "Accept": "application/json",
                                "Content-Type": "application/json",
                                "X-API-Key": self.parse_api_key,
                            },
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.request(
                            method,
                            f"{self.parse_base_url}/{endpoint.lstrip('/')}",
                            headers={"Accept": "application/json", "Content-Type": "application/json", "X-API-Key": self.parse_api_key},
                            **kwargs,
                        )
                        raise SportyBetError(
                            str(
                                payload.get("message") or "Parse provider returned an error"
                            )
                        )
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue
                    response.raise_for_status()
                    payload = response.json()
            raise SportyBetError(
                f"Parse SportyBet request failed: {last_error or 'unknown error'}"
            ) from last_error
                        raise SportyBetError("Parse provider returned invalid JSON")
                    if payload.get("status") == "error":
                        raise SportyBetError(str(payload.get("message") or "Parse provider returned an error"))
                    return payload
                except SportyBetError as exc:
                    last_error = exc
                    break
                except (httpx.HTTPError, ValueError) as exc:
            params: dict[str, Any] = {
                "page": page,
                "page_size": min(page_size, 100),
                "hours": hours,
            }
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    break
            raise SportyBetError(f"Parse SportyBet request failed: {last_error or 'unknown error'}") from last_error

    async def get_upcoming_events(
        self,
        *,
        page: int = 1,
        page_size: int = 100,
        hours: int = 168,
        market_ids: str | None = None,
    ) -> tuple[list[ProviderEvent], int]:
        if self.provider == "parse":
            params: dict[str, Any] = {"page": page, "page_size": min(page_size, 100), "hours": hours}
            if market_ids:
                params["market"] = market_ids
            payload = await self._request("GET", "get_prematch_football_markets", params=params)
            data = payload.get("data") or payload
            return self._normalize_parse_outcomes(data.get("outcomes") or [])

        params: dict[str, Any] = {
            "sportId": "sr:sport:1",
            "pageNum": page,
            "pageSize": min(page_size, 100),
            "todayGames": "false",
            "timeline": hours,
            "_t": int(time.time() * 1000),
        }
            payload = await self._request(
                "GET",
                "get_football_event_markets",
                params={"event_id": event_id},
            )
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
        if self.provider == "parse":
            payload = await self._request("GET", "get_football_event_markets", params={"event_id": event_id})
            data = payload.get("data") or payload
            events, _ = self._normalize_parse_outcomes(data.get("outcomes") or [])
            if not events:
                raise SportyBetError(f"Event {event_id} was not found")
            return events[0]
        events, _ = await self.get_upcoming_events(page=1, page_size=100)
        for event in events:
            if event.id == event_id:
                return event
        raise SportyBetError(f"Event {event_id} was not found in the current feed")

    async def create_booking(self, selections: list[dict[str, str | None]]) -> dict[str, Any]:
        if self.provider == "parse":
            payload = {"selections": json.dumps([
                {
    def _normalize_parse_outcomes(
        outcomes: list[dict[str, Any]],
    ) -> tuple[list[ProviderEvent], int]:
                    "marketId": item["market_id"],
                    **({"specifier": item["specifier"]} if item.get("specifier") else {}),
                    "outcomeId": item["outcome_id"],
                }
                for item in selections
            ])}
            return await self._request("POST", "book_bet", json=payload)

        payload = {
                "start_time": SportyBetClient._parse_start_time(
                    raw.get("estimateStartTime") or raw.get("kickoffTime")
                ),
                {
                    "eventId": item["event_id"],
                    "marketId": item["market_id"],
                    "specifier": item.get("specifier"),
                    "outcomeId": item["outcome_id"],
                }
                for item in selections
            market = event["markets"].setdefault(
                key,
                {"description": str(raw.get("marketDesc") or ""), "outcomes": []},
            )
        }
        return await self._request("POST", f"/api/{self.region}/orders/share", json=payload)


    @staticmethod
    def _normalize_parse_outcomes(outcomes: list[dict[str, Any]]) -> tuple[list[ProviderEvent], int]:
        grouped: dict[str, dict[str, Any]] = {}
        for raw in outcomes:
            event_id = raw.get("eventId")
            if event_id is None:
                    active=(
                        str(raw_event["status"]).lower()
                        not in {"closed", "finished", "cancelled", "suspended"},
                    ),
            event_id = str(event_id)
            event = grouped.setdefault(event_id, {
                "tournament_id": raw.get("tournamentId"),
                tournament_id=(
                    str(raw_event["tournament_id"])
                    if raw_event["tournament_id"] is not None else None
                ),
                "home_team": str(raw.get("homeTeamName") or ""),
                "away_team": str(raw.get("awayTeamName") or ""),
                "start_time": SportyBetClient._parse_start_time(raw.get("estimateStartTime") or raw.get("kickoffTime")),
                "status": str(raw.get("matchStatus") or "Not start"),
                "markets": {},
            })
            market_id = raw.get("marketId")
            outcome_id = raw.get("outcomeId")
            if market_id is None or outcome_id is None or raw.get("odds") is None:
                continue
            specifier = raw.get("specifier")
            key = (str(market_id), str(specifier) if specifier is not None else None)
            market = event["markets"].setdefault(key, {"description": str(raw.get("marketDesc") or ""), "outcomes": []})
            market["outcomes"].append(ProviderOutcome(
                id=str(outcome_id),
                description=str(raw.get("outcomeDesc") or ""),
                odds=Decimal(str(raw["odds"])),
                active=True,
            ))
        events: list[ProviderEvent] = []
        for event_id, raw_event in grouped.items():
            markets = tuple(
                ProviderMarket(
                    id=market_id,
                    description=data["description"],
                    specifier=specifier,
                    active=str(raw_event["status"]).lower() not in {"closed", "finished", "cancelled", "suspended"},
                    outcomes=tuple(data["outcomes"]),
                )
                for (market_id, specifier), data in raw_event["markets"].items()
            )
            events.append(ProviderEvent(
                id=event_id,
                tournament_id=str(raw_event["tournament_id"]) if raw_event["tournament_id"] is not None else None,
                tournament_name=raw_event["tournament_name"],
                home_team=raw_event["home_team"],
                away_team=raw_event["away_team"],
                start_time=raw_event["start_time"],
                status=raw_event["status"],
                markets=markets,
            ))
        events.sort(key=lambda item: item.start_time)
        return events, len(events)

    @staticmethod
    def _parse_start_time(value: Any) -> datetime:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.fromtimestamp(0, tz=timezone.utc)

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
