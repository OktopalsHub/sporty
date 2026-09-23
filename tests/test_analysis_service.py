from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.domain.analysis import AnalysisProvider
from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.services.analysis_service import AnalysisService


def prediction() -> Prediction:
    return Prediction(
        id="p1",
        event_id="e1",
        home_team="Home",
        away_team="Away",
        start_time=datetime.now(timezone.utc),
        market=Market.OVER_2_5,
        market_id="m1",
        specifier="total=2.5",
        outcome_id="o1",
        selection="Over 2.5",
        odds=Decimal("1.80"),
        probability=1 / 1.8,
        confidence=Confidence.MEDIUM,
        reasons=("Baseline reason",),
    )


@pytest.mark.asyncio
async def test_without_gemini_keeps_baseline() -> None:
    result = await AnalysisService().analyze(prediction())
    assert result.provider == AnalysisProvider.BASELINE
    assert result.probability == pytest.approx(1 / 1.8)


class FakeGemini:
    model = "fake-model"

    async def analyze(self, context: dict) -> dict:
        assert context["market"] == "over_2_5"
        return {
            "probability": 0.72,
            "confidence": "high",
            "reasons": ("Model-supported reason",),
        }


@pytest.mark.asyncio
async def test_gemini_result_is_structured() -> None:
    result = await AnalysisService(FakeGemini()).analyze(prediction())
    assert result.provider == AnalysisProvider.GEMINI
    assert result.model == "fake-model"
    assert result.probability == 0.72
    assert result.confidence == "high"
