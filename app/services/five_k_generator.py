from __future__ import annotations

import random
from decimal import Decimal

from app.domain.predictions import Prediction
from app.domain.tickets import Ticket
from app.services.odds_optimizer import OddsOptimizer


class FiveKGenerator:
    """Builds a randomized 5K accumulator from a qualified candidate pool.

    Randomness is applied only after candidates are filtered and scored.
    This prevents "random" from meaning arbitrary or low-quality selections.
    """

    TARGET_ODDS = Decimal("5000")

    def __init__(
        self,
        optimizer: OddsOptimizer | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.optimizer = optimizer or OddsOptimizer()
        self.rng = rng or random.Random()

    def generate(
        self,
        predictions: list[Prediction],
        *,
        min_probability: float = 0.55,
        candidate_pool_size: int = 150,
        attempts: int = 25,
    ) -> Ticket | None:
        candidates = [
            prediction
            for prediction in predictions
            if prediction.probability >= min_probability
            and prediction.odds > Decimal("1")
        ]

        candidates = self._qualified_pool(candidates, candidate_pool_size)
        if not candidates:
            return None

        best: Ticket | None = None

        for _ in range(max(1, attempts)):
            shuffled = candidates[:]
            self.rng.shuffle(shuffled)

            result = self.optimizer.optimize(
                shuffled,
                self.TARGET_ODDS,
                beam_width=250,
            )
            if result is None:
                continue

            ticket = Ticket(
                strategy="5k_random",
                target_odds=result.target_odds,
                actual_odds=result.actual_odds,
                selections=result.selections,
            )

            if best is None or self._ticket_score(ticket) > self._ticket_score(best):
                best = ticket

        return best

    @staticmethod
    def _qualified_pool(
        predictions: list[Prediction],
        size: int,
    ) -> list[Prediction]:
        # Keep the strongest candidates from each event so one fixture cannot
        # dominate the randomized pool.
        grouped: dict[str, list[Prediction]] = {}
        for prediction in predictions:
            grouped.setdefault(prediction.event_id, []).append(prediction)

        for event_predictions in grouped.values():
            event_predictions.sort(
                key=lambda item: item.probability,
                reverse=True,
            )

        ordered = sorted(
            (items[0] for items in grouped.values()),
            key=lambda item: item.probability,
            reverse=True,
        )

        return ordered[: max(1, size)]

    @staticmethod
    def _ticket_score(ticket: Ticket) -> float:
        if not ticket.selections:
            return 0.0

        # Prefer stronger individual candidates while still meeting the target.
        return sum(item.probability for item in ticket.selections) / len(ticket.selections)
