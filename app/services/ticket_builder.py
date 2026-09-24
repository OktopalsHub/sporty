from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from app.domain.predictions import Prediction
from app.providers.sportybet.client import SportyBetClient, SportyBetError
from app.services.selection_service import SelectionNotFoundError, SelectionService
from app.services.ticket_history_service import TicketHistoryService


class TicketBuildError(ValueError):
    """Raised when the selected predictions cannot be built into a ticket."""


@dataclass(frozen=True)
class TicketBuildResult:
    session_id: str
    selections: tuple[Prediction, ...]
    combined_odds: Decimal
    provider_response: dict[str, Any]


class TicketBuilder:
    """Builds a SportyBet share ticket from the user's exact selections.

    The builder never generates, replaces, or adds selections. It only validates
    the stored event/market/outcome IDs against the current provider feed and
    sends those exact IDs to SportyBet.
    """

    def __init__(
        self,
        selection_service: SelectionService,
        provider: SportyBetClient,
        history_service: TicketHistoryService | None = None,
    ) -> None:
        self.selection_service = selection_service
        self.provider = provider
        self.history_service = history_service

    async def build(self, session_id: str) -> TicketBuildResult:
        try:
            session = self.selection_service.get_session(session_id)
        except SelectionNotFoundError as exc:
            raise TicketBuildError("Selection session not found") from exc

        selections = tuple(session.selections.values())
        if not selections:
            raise TicketBuildError("Cannot build a ticket from an empty selection session")

        selections = await self._validate_current_selections(selections)

        combined_odds = Decimal("1")
        for selection in selections:
            combined_odds *= selection.odds

        provider_response = await self.provider.create_booking(
            [
                {
                    "event_id": selection.event_id,
                    "market_id": selection.market_id,
                    "specifier": selection.specifier,
                    "outcome_id": selection.outcome_id,
                }
                for selection in selections
            ]
        )

        if self.history_service is not None:
            self.history_service.record(
                session_id=session_id,
                combined_odds=combined_odds.quantize(Decimal("0.01")),
                selection_count=len(selections),
                provider_response=provider_response,
            )

        return TicketBuildResult(
            session_id=session_id,
            selections=selections,
            combined_odds=combined_odds.quantize(Decimal("0.01")),
            provider_response=provider_response,
        )

    async def _validate_current_selections(
        self,
        selections: tuple[Prediction, ...],
    ) -> tuple[Prediction, ...]:
        refreshed: list[Prediction] = []
        for selection in selections:
            try:
                event = await self.provider.get_event_markets(selection.event_id)
            except SportyBetError as exc:
                raise TicketBuildError(
                    f"Selected event {selection.event_id} is no longer available"
                ) from exc

            if event.status.lower() in {"closed", "finished", "cancelled"}:
                raise TicketBuildError(
                    f"Selected event {selection.event_id} is no longer available"
                )

            market = next(
                (
                    item
                    for item in event.markets
                    if item.id == selection.market_id
                    and item.specifier == selection.specifier
                    and item.active
                ),
                None,
            )
            if market is None:
                raise TicketBuildError(
                    f"Selected market {selection.market_id} for event "
                    f"{selection.event_id} is no longer available"
                )

            outcome = next(
                (
                    item
                    for item in market.outcomes
                    if item.id == selection.outcome_id and item.active
                ),
                None,
            )
            if outcome is None:
                raise TicketBuildError(
                    f"Selected outcome {selection.outcome_id} for event "
                    f"{selection.event_id} is no longer available"
                )

            refreshed.append(replace(selection, odds=outcome.odds))

        return tuple(refreshed)
