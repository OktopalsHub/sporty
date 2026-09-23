from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.markets import Market
from app.providers.sportybet.client import SportyBetClient, SportyBetError
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])


class PredictionRequest(BaseModel):
    market: Market
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=100)
    hours: int = Field(default=168, ge=1, le=720)


class PredictionResponse(BaseModel):
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
    reasons: list[str]


@router.post("/generate", response_model=list[PredictionResponse])
async def generate_predictions(request: PredictionRequest) -> list[PredictionResponse]:
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

    predictions = service.generate(events, request.market)
    return [
        PredictionResponse(
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
            confidence=item.confidence.value,
            reasons=list(item.reasons),
        )
        for item in predictions
    ]
