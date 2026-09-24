from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.markets import Market
from app.domain.predictions import Confidence
from app.providers.sportybet.client import SportyBetClient, SportyBetError
from app.services.market_generator import MarketGenerator
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/generators", tags=["generators"])


class GeneratorRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=100)
    hours: int = Field(default=168, ge=1, le=720)
    min_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: list[Confidence] | None = None


class GeneratedPredictionResponse(BaseModel):
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
    confidence: Confidence
    reasons: list[str]


class GeneratorResponse(BaseModel):
    market: Market
    total_candidates: int
    predictions: list[GeneratedPredictionResponse]


async def _generate(market: Market, request: GeneratorRequest) -> GeneratorResponse:
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

    predictions = service.generate(events, market)
    result = MarketGenerator().generate(
        predictions,
        market,
        min_probability=request.min_probability,
        confidence=set(request.confidence) if request.confidence else None,
    )

    return GeneratorResponse(
        market=result.market,
        total_candidates=result.total_candidates,
        predictions=[
            GeneratedPredictionResponse(
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
                reasons=list(item.reasons),
            )
            for item in result.predictions
        ],
    )


@router.post("/over-1-5/generate", response_model=GeneratorResponse)
async def generate_over_1_5(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.OVER_1_5, request)


@router.post("/over-2-5/generate", response_model=GeneratorResponse)
async def generate_over_2_5(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.OVER_2_5, request)


@router.post("/btts/generate", response_model=GeneratorResponse)
async def generate_btts(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.BTTS, request)


@router.post("/under-2-5/generate", response_model=GeneratorResponse)
async def generate_under_2_5(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.UNDER_2_5, request)


@router.post("/under-4-5/generate", response_model=GeneratorResponse)
async def generate_under_4_5(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.UNDER_4_5, request)
