from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.services.weekly_safe_generator import WeeklySafeGenerator


def make_prediction(index: int, *, probability: float = 0.85) -> Prediction:
    return Prediction(
        id=str(index),
        event_id=f"event-{index}",
        home_team=f"Home {index}",
        away_team=f"Away {index}",
        start_time=datetime(2026, 9, 20, tzinfo=timezone.utc) + timedelta(days=index % 5),
        market=Market.OVER_1_5,
        market_id="18",
        specifier="total=1.5",
        outcome_id=str(index),
        selection="Over 1.5",
        odds=Decimal("2.50"),
        probability=probability,
        confidence=Confidence.VERY_HIGH,
    )


def test_weekly_safe_reaches_10k_and_covers_multiple_days():
    ticket = WeeklySafeGenerator().generate([make_prediction(i) for i in range(12)])

    assert ticket is not None
    assert ticket.actual_odds >= Decimal("10000")
    assert len(ticket.selections) == 9
    assert len({item.start_time.date() for item in ticket.selections}) >= 3


def test_weekly_safe_rejects_low_confidence_candidates():
    candidates = [make_prediction(i, probability=0.60) for i in range(20)]

    assert WeeklySafeGenerator().generate(candidates) is None


def test_weekly_safe_never_reuses_an_event():
    predictions = [make_prediction(0), make_prediction(1)]
    duplicate = make_prediction(2)
    duplicate = Prediction(
        **{**duplicate.__dict__, "event_id": "event-0", "id": "duplicate"}
    )

    ticket = WeeklySafeGenerator().generate(predictions + [duplicate])

    assert ticket is not None
    assert len({item.event_id for item in ticket.selections}) == len(ticket.selections)
