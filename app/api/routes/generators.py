from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

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
    market_name: str | None = None
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
            page=request.page, page_size=request.page_size, hours=request.hours, market_ids=market_filter
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
                id=item.id, event_id=item.event_id, home_team=item.home_team,
                away_team=item.away_team, market=item.market, market_name=item.market_name,
                market_id=item.market_id, specifier=item.specifier, outcome_id=item.outcome_id,
                selection=item.selection, odds=str(item.odds), probability=item.probability,
                confidence=item.confidence, reasons=list(item.reasons),
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


class CustomGeneratorRequest(BaseModel):
    target_odds: Decimal = Field(gt=1, le=Decimal("100000"))
    hours: int = Field(default=168, ge=1, le=720)
    market_filter: str | None = Field(default=None, min_length=1)
    # Backwards-compatible API field. When omitted, all provider markets are used.
    markets: list[Market] | None = None


class CustomSelection(GeneratedPredictionResponse):
    pass


class CustomGeneratorResponse(BaseModel):
    target_odds: str
    actual_odds: str
    selection_count: int
    selections: list[CustomSelection]


def _selected_market(value: str | None) -> Market | None:
    if not value:
        return None
    aliases = {
        "over_1_5": Market.OVER_1_5,
        "over_2_5": Market.OVER_2_5,
        "under_2_5": Market.UNDER_2_5,
        "under_4_5": Market.UNDER_4_5,
        "btts": Market.BTTS,
        "double_chance": Market.DOUBLE_CHANCE,
        "match_result": Market.MATCH_RESULT,
    }
    return aliases.get(value.lower().strip())


@router.post("/custom/generate", response_model=CustomGeneratorResponse)
async def generate_custom(request: CustomGeneratorRequest) -> CustomGeneratorResponse:
    """Build a ticket from the exact selected market, or all available provider markets."""
    client = SportyBetClient()
    service = PredictionService()
    optimizer = OddsOptimizer()
    selected_market = _selected_market(request.market_filter)

    if request.market_filter and selected_market is None:
        raise HTTPException(
            status_code=422,
            detail="Unknown market filter. Use over_1_5, over_2_5, under_2_5, under_4_5, btts, double_chance, or match_result.",
        )

    if selected_market is None and request.markets:
        if len(request.markets) == 1 and request.markets[0] != Market.ALL:
            selected_market = request.markets[0]

    # Important: one provider request per page. The old implementation made
    # four provider calls per page, which could exceed the deployment gateway timeout.
    max_pages = 3
    try:
        for page in range(1, max_pages + 1):
            events, _ = await client.get_upcoming_events(
                page=page,
                page_size=25,
                hours=request.hours,
                market_ids=None,
            )
            if not events:
                break

            all_events = events
            if selected_market is None:
                predictions = service.generate_all_available(all_events)
            else:
                predictions = service.generate(all_events, selected_market)

            result = await run_in_threadpool(
                optimizer.optimize,
                predictions,
                request.target_odds,
                beam_width=500,
            )
            if result is not None:
                return CustomGeneratorResponse(
                    target_odds=str(result.target_odds),
                    actual_odds=str(result.actual_odds),
                    selection_count=len(result.selections),
                    selections=[
                        CustomSelection(
                            id=item.id, event_id=item.event_id, home_team=item.home_team,
                            away_team=item.away_team, market=item.market,
                            market_name=item.market_name, market_id=item.market_id,
                            specifier=item.specifier, outcome_id=item.outcome_id,
                            selection=item.selection, odds=str(item.odds),
                            probability=item.probability, confidence=item.confidence,
                            reasons=list(item.reasons),
                        )
                        for item in result.selections
                    ],
                )
    except SportyBetError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    raise HTTPException(
        status_code=422,
        detail=f"Could not build a ticket reaching {request.target_odds} odds from the available markets.",
    )
