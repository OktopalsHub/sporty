from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.domain.provider import ProviderEvent
from app.providers.sportybet.client import SportyBetClient, SportyBetError
from app.services.prediction_service import PredictionService
from app.services.weekly_safe_generator import WeeklySafeGenerator

router = APIRouter(prefix="/generators/weekly-safe", tags=["generators"])


class WeeklySafeRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    hours: int = Field(default=168, ge=1, le=720)
    min_probability: float = Field(default=0.75, ge=0.0, le=1.0)
    min_confidence: Confidence = Confidence.HIGH
    min_days: int = Field(default=3, ge=1, le=7)
    candidate_limit_per_day: int = Field(default=40, ge=1, le=200)


class WeeklySafeSelection(BaseModel):
    id: str
    event_id: str
    home_team: str
    away_team: str
    start_time: str
    market: Market
    market_id: str
    specifier: str | None
    outcome_id: str
    selection: str
    odds: str
    probability: float
    confidence: str


class WeeklySafeResponse(BaseModel):
    strategy: str
    target_odds: str
    actual_odds: str
    selection_count: int
    covered_days: int
    selections: list[WeeklySafeSelection]


@router.post("/generate", response_model=WeeklySafeResponse)
async def generate_weekly_safe(request: WeeklySafeRequest) -> WeeklySafeResponse:
    client = SportyBetClient()
    service = PredictionService()

    try:
        # Fetch only the two market families used by the weekly strategy.
        # This keeps Parse responses small enough for the hosted API timeout.
        market_events: dict[str, ProviderEvent] = {}
        for market_filter in ("Over/Under", "GG/NG"):
            filtered_events, _ = await client.get_upcoming_events(
                page=request.page,
                page_size=request.page_size,
                hours=request.hours,
                market_ids=market_filter,
            )
            for event in filtered_events:
                existing = market_events.get(event.id)
                if existing is None:
                    market_events[event.id] = event
                else:
                    merged_markets = tuple(existing.markets) + tuple(
                        market for market in event.markets
                        if (market.id, market.specifier) not in {
                            (item.id, item.specifier) for item in existing.markets
                        }
                    )
                    market_events[event.id] = ProviderEvent(
                        id=existing.id,
                        tournament_id=existing.tournament_id,
                        tournament_name=existing.tournament_name,
                        home_team=existing.home_team,
                        away_team=existing.away_team,
                        start_time=existing.start_time,
                        status=existing.status,
                        markets=merged_markets,
                    )
        events = list(market_events.values())
    except SportyBetError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    predictions: list[Prediction] = []
    for market in Market:
        predictions.extend(service.generate(events, market))

    ticket = WeeklySafeGenerator().generate(
        predictions,
        min_probability=request.min_probability,
        min_confidence=request.min_confidence,
        min_days=request.min_days,
        candidate_limit_per_day=request.candidate_limit_per_day,
    )
    if ticket is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "No high-confidence weekly candidate combination can reach "
                "10000 combined odds while covering the requested days."
            ),
        )

    covered_days = len({item.start_time.date() for item in ticket.selections})
    return WeeklySafeResponse(
        strategy=ticket.strategy,
        target_odds=str(ticket.target_odds),
        actual_odds=str(ticket.actual_odds),
        selection_count=len(ticket.selections),
        covered_days=covered_days,
        selections=[
            WeeklySafeSelection(
                id=item.id,
                event_id=item.event_id,
                home_team=item.home_team,
                away_team=item.away_team,
                start_time=item.start_time.isoformat(),
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
