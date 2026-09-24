from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from decimal import Decimal

from app.domain.markets import Market
from app.domain.predictions import Confidence
from app.providers.sportybet.client import SportyBetClient, SportyBetError
from app.services.market_generator import MarketGenerator
from app.services.prediction_service import PredictionService
from app.services.odds_optimizer import OddsOptimizer

router = APIRouter(prefix="/generators", tags=["generators"])


class GeneratorRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=25)
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
        market_filter = "GG/NG" if market == Market.BTTS else "Over/Under"
        events, _ = await client.get_upcoming_events(
            page=request.page,
            page_size=request.page_size,
            hours=request.hours,
            market_ids=market_filter,
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


@router.post("/over-2-5/generate", response_model=GeneratorResponse)
async def generate_over_2_5(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.OVER_2_5, request)


@router.post("/btts/generate", response_model=GeneratorResponse)
async def generate_btts(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.BTTS, request)


@router.post("/under-2-5/generate", response_model=GeneratorResponse)
async def generate_under_2_5(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.UNDER_2_5, request)


@router.post("/over-1-5/generate", response_model=GeneratorResponse)
async def generate_under_4_5(request: GeneratorRequest) -> GeneratorResponse:
    return await _generate(Market.OVER_1_5, request)


class CustomGeneratorRequest(BaseModel):
    target_odds: Decimal = Field(gt=1)
    hours: int = Field(default=168, ge=1, le=720)
    markets: list[Market] = Field(
        default_factory=lambda: [
            Market.OVER_2_5,
            Market.BTTS,
            Market.UNDER_2_5,
            Market.OVER_1_5,
        ],
        min_length=1,
    )


class CustomSelection(GeneratedPredictionResponse):
    pass


class CustomGeneratorResponse(BaseModel):
    target_odds: str
    actual_odds: str
    selection_count: int
    selections: list[CustomSelection]


@router.post("/custom/generate", response_model=CustomGeneratorResponse)
async def generate_custom(request: CustomGeneratorRequest) -> CustomGeneratorResponse:
    client = SportyBetClient()
    service = PredictionService()
    market_filters = {
        Market.BTTS: "GG/NG",
        Market.OVER_2_5: "Over/Under",
        Market.UNDER_2_5: "Over/Under",
        Market.OVER_1_5: "Over/Under",
    }

    events_by_id = {}
    try:
        # Walk provider pages instead of asking the UI for a fixed match count.
        # Stop as soon as the optimizer has enough candidates for the requested odds.
        for page in range(1, 21):
            for market in request.markets:
                events, total = await client.get_upcoming_events(
                    page=page,
                    page_size=25,
                    hours=request.hours,
                    market_ids=market_filters[market],
                )
                for event in events:
                    existing = events_by_id.get(event.id)
                    if existing is None:
                        events_by_id[event.id] = event
                    else:
                        merged = list(existing.markets)
                        known = {(m.id, m.specifier) for m in merged}
                        merged.extend(
                            m for m in event.markets
                            if (m.id, m.specifier) not in known
                        )
                        events_by_id[event.id] = event.__class__(
                            id=existing.id,
                            tournament_id=existing.tournament_id,
                            tournament_name=existing.tournament_name,
                            home_team=existing.home_team,
                            away_team=existing.away_team,
                            start_time=existing.start_time,
                            status=existing.status,
                            markets=tuple(merged),
                        )
                predictions = []
                for selected_market in request.markets:
                    predictions.extend(service.generate(list(events_by_id.values()), selected_market))
                result = OddsOptimizer().optimize(predictions, request.target_odds, beam_width=500)
                if result is not None:
                    return CustomGeneratorResponse(
                        target_odds=str(result.target_odds),
                        actual_odds=str(result.actual_odds),
                        selection_count=len(result.selections),
                        selections=[
                            CustomSelection(
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
                            for item in result.selections
                        ],
                    )
                if total and page * 25 >= total:
                    break
    except SportyBetError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    raise HTTPException(
        status_code=422,
        detail=f"Could not build a ticket reaching {request.target_odds} odds from the available priority markets.",
    )
