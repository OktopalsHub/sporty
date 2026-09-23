from __future__ import annotations

from app.domain.analysis import AnalysisProvider, PredictionAnalysis
from app.domain.predictions import Prediction
from app.providers.gemini.client import GeminiClient, GeminiError


class AnalysisService:
    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini = gemini

    async def analyze(self, prediction: Prediction) -> PredictionAnalysis:
        if self.gemini is None:
            return PredictionAnalysis(
                probability=prediction.probability,
                confidence=prediction.confidence.value,
                reasons=prediction.reasons,
                provider=AnalysisProvider.BASELINE,
            )

        try:
            result = await self.gemini.analyze(
                {
                    "event": {
                        "id": prediction.event_id,
                        "home_team": prediction.home_team,
                        "away_team": prediction.away_team,
                        "start_time": prediction.start_time.isoformat(),
                    },
                    "market": prediction.market.value,
                    "selection": prediction.selection,
                    "odds": str(prediction.odds),
                    "baseline_probability": prediction.probability,
                }
            )
        except GeminiError:
            return PredictionAnalysis(
                probability=prediction.probability,
                confidence=prediction.confidence.value,
                reasons=prediction.reasons + (
                    "Gemini analysis was unavailable; baseline odds analysis was retained.",
                ),
                provider=AnalysisProvider.BASELINE,
            )

        return PredictionAnalysis(
            probability=result["probability"],
            confidence=result["confidence"],
            reasons=tuple(result["reasons"]),
            provider=AnalysisProvider.GEMINI,
            model=self.gemini.model,
        )
