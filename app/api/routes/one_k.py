import asyncio
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.markets import Market
from app.domain.predictions import Prediction
from app.providers.sportybet.client import SportyBetClient, SportyBetError
from app.services.one_k_generator import OneKGenerator
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/generators/1k", tags=["generators"])


class OneKRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=100)
    hours: int = Field(default=168, ge=1, le=720)
    min_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class OneKSelection(BaseModel):
    id: str
    event_id: str
    home_team: str
    away_team: str
    market: Market
    market_id: str
    specifier: str | None
    outcome_id: str
    selection: str
    odds: str
    probability: float
    confidence: str


class OneKResponse(BaseModel):
    strategy: str
    target_odds: str
    actual_odds: str
    selection_count: int
    selections: list[OneKSelection]


@router.post("/generate", response_model=OneKResponse)
async def generate_1k(request: OneKRequest) -> OneKResponse:
    client = SportyBetClient()
    service = PredictionService()

    try:
        events, _ = await client.get_upcoming_events(
            page=request.page,
            page_size=request.page_size,
            hours=request.hours,
        )
    except SportyBetError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    predictions: list[Prediction] = []
    for market in Market:
        predictions.extend(service.generate(events, market))

    predictions = [
        item for item in predictions if item.probability >= request.min_probability
    ]

    ticket = await asyncio.to_thread(OneKGenerator().generate, predictions)
    if ticket is None:
        raise HTTPException(
            status_code=422,
            detail="No available candidate combination can reach 1000 combined odds.",
        )

    return OneKResponse(
        strategy=ticket.strategy,
        target_odds=str(ticket.target_odds),
        actual_odds=str(ticket.actual_odds),
        selection_count=len(ticket.selections),
        selections=[
            OneKSelection(
                id=item.id,
                event_id=item.event_id,
                home_team=item.home_team,
                away_team=item.away_team,
                market=item.market,
                market_id=item.market_id,
                specifier=item.specifier,
                outcome_id=item.outcome_id,
                selection=item.selection,
                odds=str(item.odds),
                probability=item.probability,
                confidence=item.confidence,
            )
            for item in ticket.selections
        ],
    )
