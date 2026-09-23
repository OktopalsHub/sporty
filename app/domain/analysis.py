from dataclasses import dataclass
from enum import StrEnum


class AnalysisProvider(StrEnum):
    BASELINE = "baseline"
    GEMINI = "gemini"


@dataclass(frozen=True)
class PredictionAnalysis:
    probability: float
    confidence: str
    reasons: tuple[str, ...]
    provider: AnalysisProvider
    model: str | None = None
