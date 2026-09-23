from datetime import datetime\nfrom decimal import Decimal\nimport hashlib

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.services.selection_service import (
    SelectionConflictError,
    SelectionNotFoundError,
    SelectionService,
)

router = APIRouter(prefix="/selections", tags=["selections"])
selection_service = SelectionService()


class SelectionInput(BaseModel):
    id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)\n    start_time: datetime
    home_team: str
    away_team: str
    market: Market
    market_id: str
    specifier: str | None = None
    outcome_id: str
    selection: str
    odds: Decimal = Field(gt=1)
    probability: float = Field(ge=0.0, le=1.0)
    confidence: Confidence
    reasons: list[str] = Field(default_factory=list)


class SelectionResponse(SelectionInput):
    pass


class SelectionSessionResponse(BaseModel):
    session_id: str
    selection_count: int
    combined_odds: str
    selections: list[SelectionResponse]


def _to_prediction(item: SelectionInput) -> Prediction:
    # start_time is not part of the Phase 9 client contract yet. Selection
    # keeps the exact generated market/outcome IDs and odds for later ticket
    # building; the event date can be refreshed when booking is implemented.
    from datetime import datetime, timezone

    return Prediction(
        id=item.id,
        event_id=item.event_id,
        home_team=item.home_team,
        away_team=item.away_team,
        start_time=item.start_time,
        market=item.market,
        market_id=item.market_id,
        specifier=item.specifier,
        outcome_id=item.outcome_id,
        selection=item.selection,
        odds=item.odds,
        probability=item.probability,
        confidence=item.confidence,
        reasons=tuple(item.reasons),
    )


def _response(session_id: str) -> SelectionSessionResponse:
    session = selection_service.get_session(session_id)
    selections = tuple(session.selections.values())
    combined = Decimal("1")
    for item in selections:
        combined *= item.odds

    return SelectionSessionResponse(
        session_id=session.id,
        selection_count=len(selections),
        combined_odds=str(combined.quantize(Decimal("0.01"))),
        selections=[
            SelectionResponse(
                id=item.id,
                event_id=item.event_id,
                home_team=item.home_team,
                away_team=item.away_team,
                market=item.market,
                market_id=item.market_id,
                specifier=item.specifier,
                outcome_id=item.outcome_id,
                selection=item.selection,
                odds=item.odds,
                probability=item.probability,
                confidence=item.confidence,
                reasons=list(item.reasons),
            )
            for item in selections
        ],
    )


@router.post("/sessions", response_model=SelectionSessionResponse)
async def create_selection_session() -> SelectionSessionResponse:
    session = selection_service.create_session()
    return _response(session.id)


@router.get("/sessions/{session_id}", response_model=SelectionSessionResponse)
async def get_selection_session(session_id: str) -> SelectionSessionResponse:
    try:
        return _response(session_id)
    except SelectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Selection session not found") from exc


@router.post("/sessions/{session_id}", response_model=SelectionSessionResponse)
async def add_selection(
    session_id: str,
    selection: SelectionInput,
) -> SelectionSessionResponse:
    try:
        selection_service.add(session_id, _to_prediction(selection))
        return _response(session_id)
    except SelectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Selection session not found") from exc
    except SelectionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/sessions/{session_id}/{prediction_id}",
    response_model=SelectionSessionResponse,
)
async def remove_selection(
    session_id: str,
    prediction_id: str,
) -> SelectionSessionResponse:
    try:
        selection_service.remove(session_id, prediction_id)
        return _response(session_id)
    except SelectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Selection or session not found") from exc


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_selection_session(session_id: str) -> Response:
    try:
        selection_service.delete_session(session_id)
        return Response(status_code=204)
    except SelectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Selection session not found") from exc
