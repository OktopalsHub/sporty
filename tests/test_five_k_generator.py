from datetime import datetime, timezone
from decimal import Decimal
import random

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.services.five_k_generator import FiveKGenerator


def prediction(event_id: str, prediction_id: str, odds: str, probability: float) -> Prediction:
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


def test_5k_uses_qualified_pool_and_reaches_target() -> None:
    candidates = [
        prediction(f"event-{i}", str(i), "2.50", 0.70)
        for i in range(12)
    ]

    ticket = FiveKGenerator(rng=random.Random(7)).generate(
        candidates,
        min_probability=0.65,
        candidate_pool_size=12,
        attempts=10,
    )

    assert ticket is not None
    assert ticket.actual_odds >= Decimal("5000")
    assert len(ticket.selections) >= 9


def test_5k_never_uses_duplicate_events() -> None:
    candidates = [
        prediction("event-1", "a", "10.00", 0.90),
        prediction("event-1", "b", "9.00", 0.89),
        prediction("event-2", "c", "10.00", 0.90),
        prediction("event-3", "d", "10.00", 0.90),
    ]

    ticket = FiveKGenerator(rng=random.Random(2)).generate(
        candidates,
        min_probability=0.80,
        candidate_pool_size=10,
        attempts=10,
    )

    assert ticket is None or len({x.event_id for x in ticket.selections}) == len(ticket.selections)


def test_5k_rejects_low_probability_candidates() -> None:
    candidates = [
        prediction(f"event-{i}", str(i), "10.00", 0.40)
        for i in range(10)
    ]

    assert FiveKGenerator().generate(candidates, min_probability=0.55) is None
