from datetime import datetime, timezone
from decimal import Decimal

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.services.market_generator import MarketGenerator


def make_prediction(
    prediction_id: str,
    market: Market,
    probability: float,
    confidence: Confidence = Confidence.HIGH,
) -> Prediction:
    return Prediction(
        id=prediction_id,
        event_id=f"event-{prediction_id}",
        home_team="Home",
        away_team="Away",
        start_time=datetime.now(timezone.utc),
        market=market,
        market_id="market-1",
        specifier=None,
        outcome_id=f"outcome-{prediction_id}",
        selection="Selection",
        odds=Decimal("1.80"),
        probability=probability,
        confidence=confidence,
        reasons=("test",),
    )


def test_generator_only_returns_requested_market() -> None:
    predictions = [
        make_prediction("1", Market.OVER_2_5, 0.70),
        make_prediction("2", Market.BTTS, 0.80),
    ]

    result = MarketGenerator().generate(predictions, Market.OVER_2_5)

    assert result.market == Market.OVER_2_5
    assert len(result.predictions) == 1
    assert result.predictions[0].id == "1"


def test_generator_applies_probability_and_confidence_filters() -> None:
    predictions = [
        make_prediction("1", Market.UNDER_4_5, 0.80, Confidence.VERY_HIGH),
        make_prediction("2", Market.UNDER_4_5, 0.65, Confidence.MEDIUM),
    ]

    result = MarketGenerator().generate(
        predictions,
        Market.UNDER_4_5,
        min_probability=0.75,
        confidence={Confidence.VERY_HIGH},
    )

    assert [item.id for item in result.predictions] == ["1"]


def test_generator_sorts_highest_probability_first() -> None:
    predictions = [
        make_prediction("1", Market.UNDER_2_5, 0.60),
        make_prediction("2", Market.UNDER_2_5, 0.85),
    ]

    result = MarketGenerator().generate(predictions, Market.UNDER_2_5)

    assert [item.id for item in result.predictions] == ["2", "1"]
