from datetime import datetime, timezone
from decimal import Decimal

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.services.odds_optimizer import OddsOptimizer


def prediction(
    event_id: str,
    prediction_id: str,
    odds: str,
    probability: float,
) -> Prediction:
    return Prediction(
        id=prediction_id,
        event_id=event_id,
        home_team="Home",
        away_team="Away",
        start_time=datetime.now(timezone.utc),
        market=Market.OVER_2_5,
        market_id="market",
        specifier="total=2.5",
        outcome_id=prediction_id,
        selection="Over 2.5",
        odds=Decimal(odds),
        probability=probability,
        confidence=Confidence.HIGH,
        reasons=("test",),
    )


def test_reaches_target_without_fixed_selection_limit() -> None:
    candidates = [
        prediction(f"event-{i}", str(i), "2.00", 0.70)
        for i in range(12)
    ]

    result = OddsOptimizer().optimize(candidates, Decimal("1000"))

    assert result is not None
    assert result.actual_odds >= Decimal("1000")
    assert len(result.selections) >= 10


def test_does_not_select_two_markets_from_same_event() -> None:
    candidates = [
        prediction("event-1", "a", "20.00", 0.70),
        prediction("event-1", "b", "20.00", 0.69),
        prediction("event-2", "c", "20.00", 0.70),
        prediction("event-3", "d", "20.00", 0.70),
    ]

    result = OddsOptimizer().optimize(candidates, Decimal("100"))

    assert result is not None
    assert len({item.event_id for item in result.selections}) == len(result.selections)


def test_returns_none_when_target_cannot_be_reached() -> None:
    candidates = [prediction("event-1", "1", "1.10", 0.90)]

    assert OddsOptimizer().optimize(candidates, Decimal("1000")) is None
