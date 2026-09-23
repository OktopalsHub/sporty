from dataclasses import dataclass

from app.domain.markets import Market
from app.domain.predictions import Prediction


@dataclass(frozen=True)
class GeneratedPredictions:
    market: Market
    predictions: tuple[Prediction, ...]
    total_candidates: int
