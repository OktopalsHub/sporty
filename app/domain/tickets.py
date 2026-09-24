from dataclasses import dataclass
from decimal import Decimal

from app.domain.predictions import Prediction


@dataclass(frozen=True)
class Ticket:
    strategy: str
    target_odds: Decimal
    actual_odds: Decimal
    selections: tuple[Prediction, ...]
