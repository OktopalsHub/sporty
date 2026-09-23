from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.providers.sportybet.client import SportyBetClient, SportyBetError
from app.services.ticket_builder import TicketBuildError, TicketBuilder
from app.api.routes.selections import selection_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketSelectionResponse(BaseModel):
    id: str
    event_id: str
    market_id: str
    specifier: str | None
    outcome_id: str
    selection: str
    odds: Decimal


class TicketBuildResponse(BaseModel):
    session_id: str
    selection_count: int
    combined_odds: str
    selections: list[TicketSelectionResponse]
    provider_response: dict


@router.post(
    "/{session_id}/build",
    response_model=TicketBuildResponse,
)
async def build_ticket(session_id: str) -> TicketBuildResponse:
    builder = TicketBuilder(
        selection_service=selection_service,
        provider=SportyBetClient(),
    )

    try:
        result = await builder.build(session_id)
    except TicketBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SportyBetError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TicketBuildResponse(
        session_id=result.session_id,
        selection_count=len(result.selections),
        combined_odds=str(result.combined_odds),
        selections=[
            TicketSelectionResponse(
                id=item.id,
                event_id=item.event_id,
                market_id=item.market_id,
                specifier=item.specifier,
                outcome_id=item.outcome_id,
                selection=item.selection,
                odds=item.odds,
            )
            for item in result.selections
        ],
        provider_response=result.provider_response,
    )
