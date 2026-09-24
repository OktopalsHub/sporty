from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from app.domain.predictions import Prediction


@dataclass(frozen=True)
class OptimizationResult:
    target_odds: Decimal
    actual_odds: Decimal
    selections: tuple[Prediction, ...]


class OddsOptimizer:
    """Finds a high-quality accumulator at or above a target odds value.

    There is intentionally no maximum selection count. The search uses a beam
    to keep computation bounded while allowing as many legs as needed to reach
    the target. At most one selection from an event is allowed.
    """

    def optimize(
        self,
        predictions: list[Prediction],
        target_odds: Decimal = Decimal("1000"),
        *,
        beam_width: int = 500,
    ) -> OptimizationResult | None:
        if target_odds <= Decimal("1"):
            raise ValueError("target_odds must be greater than 1")

        candidates = self._prepare(predictions)
        if not candidates:
            return None

        # State: (log_odds, quality_score, selected_predictions)
        states: list[tuple[float, float, tuple[Prediction, ...]]] = [(0.0, 0.0, ())]
        target_log = math.log(float(target_odds))

        while states:
            next_states: list[tuple[float, float, tuple[Prediction, ...]]] = []

            for log_odds, quality, selected in states:
                selected_events = {item.event_id for item in selected}

                for prediction in candidates:
                    if prediction.event_id in selected_events:
                        continue

                    new_log = log_odds + math.log(float(prediction.odds))
                    new_selected = selected + (prediction,)
                    new_quality = quality + self._quality(prediction)

                    if new_log >= target_log:
                        actual = self._product_odds(new_selected)
                        return OptimizationResult(
                            target_odds=target_odds,
                            actual_odds=actual,
                            selections=new_selected,
                        )

                    next_states.append((new_log, new_quality, new_selected))

            if not next_states:
                return None

            # Keep diverse states. Prefer higher model quality while retaining
            # some states closer to the target.
            next_states.sort(
                key=lambda state: (
                    state[0] + (state[1] * 0.15),
                    state[1],
                ),
                reverse=True,
            )
            states = self._dedupe_states(next_states, beam_width)

            # The highest possible remaining odds cannot reach the target.
            max_next = max((state[0] for state in states), default=0.0)
            if max_next >= target_log:
                continue

        return None

    @staticmethod
    def _prepare(predictions: list[Prediction]) -> list[Prediction]:
        unique: dict[tuple[str, str], Prediction] = {}

        for prediction in predictions:
            if prediction.odds <= Decimal("1"):
                continue

            key = (prediction.event_id, prediction.market.value)
            current = unique.get(key)
            if current is None or OddsOptimizer._quality(prediction) > OddsOptimizer._quality(current):
                unique[key] = prediction

        return sorted(
            unique.values(),
            key=OddsOptimizer._quality,
            reverse=True,
        )

    @staticmethod
    def _quality(prediction: Prediction) -> float:
        # Probability is the main quality signal. Expected value is used only
        # as a small tie-breaker because bookmaker odds are not a true model.
        return prediction.probability + (prediction.expected_value * 0.01)

    @staticmethod
    def _product_odds(predictions: tuple[Prediction, ...]) -> Decimal:
        result = Decimal("1")
        for prediction in predictions:
            result *= prediction.odds
        return result.quantize(Decimal("0.01"))

    @staticmethod
    def _dedupe_states(
        states: list[tuple[float, float, tuple[Prediction, ...]]],
        beam_width: int,
    ) -> list[tuple[float, float, tuple[Prediction, ...]]]:
        seen: set[frozenset[str]] = set()
        result: list[tuple[float, float, tuple[Prediction, ...]]] = []

        for state in states:
            ids = frozenset(item.id for item in state[2])
            if ids in seen:
                continue
            seen.add(ids)
            result.append(state)
            if len(result) >= beam_width:
                break

        return result
