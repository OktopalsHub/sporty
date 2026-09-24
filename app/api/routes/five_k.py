from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.markets import Market
from app.domain.predictions import Prediction
from app.providers.sportybet.client import SportyBetClient, SportyBetError
from app.services.five_k_generator import FiveKGenerator
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/generators/5k", tags=["generators"])


class FiveKRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=100)
    hours: int = Field(default=168, ge=1, le=720)
    min_probability: float = Field(default=0.55, ge=0.0, le=1.0)
    candidate_pool_size: int = Field(default=150, ge=1, le=1000)
    attempts: int = Field(default=25, ge=1, le=100)


class FiveKSelection(BaseModel):
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


class FiveKResponse(BaseModel):
    strategy: str
    target_odds: str
    actual_odds: str
    selection_count: int
    candidate_pool_size: int
    selections: list[FiveKSelection]


@router.post("/generate", response_model=FiveKResponse)
async def generate_5k(request: FiveKRequest) -> FiveKResponse:
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

    ticket = FiveKGenerator().generate(
        predictions,
        min_probability=request.min_probability,
        candidate_pool_size=request.candidate_pool_size,
        attempts=request.attempts,
    )
    if ticket is None:
        raise HTTPException(
            status_code=422,
            detail="No qualified randomized candidate combination can reach 5000 combined odds.",
        )

    return FiveKResponse(
        strategy=ticket.strategy,
        target_odds=str(ticket.target_odds),
        actual_odds=str(ticket.actual_odds),
        selection_count=len(ticket.selections),
        candidate_pool_size=request.candidate_pool_size,
        selections=[
            FiveKSelection(
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
