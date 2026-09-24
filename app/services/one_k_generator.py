from __future__ import annotations

from decimal import Decimal

from app.domain.markets import Market
from app.domain.tickets import Ticket
from app.services.odds_optimizer import OddsOptimizer


class OneKGenerator:
    TARGET_ODDS = Decimal("1000")
    ALLOWED_MARKETS = frozenset(Market)

    def __init__(self, optimizer: OddsOptimizer | None = None) -> None:
        self.optimizer = optimizer or OddsOptimizer()

    def generate(self, predictions: list) -> Ticket | None:
        candidates = [
            prediction
            for prediction in predictions
            if prediction.market in self.ALLOWED_MARKETS
        ]
        result = self.optimizer.optimize(candidates, self.TARGET_ODDS)

        if result is None:
            return None

        return Ticket(
            strategy="1k",
            target_odds=result.target_odds,
            actual_odds=result.actual_odds,
            selections=result.selections,
        )
