from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.domain.markets import Market


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class Prediction:
    id: str
    event_id: str
    home_team: str
    away_team: str
    start_time: datetime
    market: Market
    market_id: str
    specifier: str | None
    outcome_id: str
    selection: str
    odds: Decimal
    probability: float
    confidence: Confidence
    reasons: tuple[str, ...] = ()
    market_name: str | None = None

    @property
    def expected_value(self) -> float:
        return self.probability * float(self.odds)
