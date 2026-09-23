from __future__ import annotations

from app.domain.generators import GeneratedPredictions
from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction


class MarketGenerator:
    """Builds market-specific candidate lists without mixing markets."""

    def generate(
        self,
        predictions: list[Prediction],
        market: Market,
        *,
        min_probability: float = 0.0,
        confidence: set[Confidence] | None = None,
    ) -> GeneratedPredictions:
        candidates = [
            prediction
            for prediction in predictions
            if prediction.market == market
            and prediction.probability >= min_probability
            and (confidence is None or prediction.confidence in confidence)
        ]

        candidates.sort(
            key=lambda item: (item.probability, -float(item.odds)),
            reverse=True,
        )

        return GeneratedPredictions(
            market=market,
            predictions=tuple(candidates),
            total_candidates=len(candidates),
        )
