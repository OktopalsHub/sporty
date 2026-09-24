from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.predictions import Confidence, Prediction
from app.domain.tickets import Ticket


@dataclass(frozen=True)
class _State:
    odds: Decimal
    probability_sum: float
    selections: tuple[Prediction, ...]
    event_ids: frozenset[str]
    days: frozenset[date]


class WeeklySafeGenerator:
    """Builds a high-confidence accumulator from fixtures across a time window.

    "Safe" describes the individual candidate filter only. The resulting
    accumulator is not guaranteed to win, and no maximum selection count is
    imposed.
    """

    TARGET_ODDS = Decimal("10000")
    DEFAULT_MIN_PROBABILITY = 0.75
    DEFAULT_MIN_DAYS = 3
    BEAM_WIDTH = 1500

    def generate(
        self,
        predictions: list[Prediction],
        *,
        min_probability: float = DEFAULT_MIN_PROBABILITY,
        min_confidence: Confidence = Confidence.HIGH,
        min_days: int = DEFAULT_MIN_DAYS,
        candidate_limit_per_day: int = 40,
    ) -> Ticket | None:
        candidates = self._prepare(
            predictions,
            min_probability=min_probability,
            min_confidence=min_confidence,
            candidate_limit_per_day=candidate_limit_per_day,
        )
        if not candidates:
            return None

        states = [
            _State(
                odds=Decimal("1"),
                probability_sum=0.0,
                selections=(),
                event_ids=frozenset(),
                days=frozenset(),
            )
        ]

        for prediction in candidates:
            day = prediction.start_time.date()
            next_states = list(states)

            for state in states:
                if prediction.event_id in state.event_ids:
                    continue

                odds = state.odds * prediction.odds
                selections = state.selections + (prediction,)
                new_state = _State(
                    odds=odds,
                    probability_sum=state.probability_sum + prediction.probability,
                    selections=selections,
                    event_ids=state.event_ids | {prediction.event_id},
                    days=state.days | {day},
                )

                if odds >= self.TARGET_ODDS and len(new_state.days) >= min_days:
                    return Ticket(
                        strategy="weekly_safe",
                        target_odds=self.TARGET_ODDS,
                        actual_odds=odds.quantize(Decimal("0.01")),
                        selections=selections,
                    )

                next_states.append(new_state)

            states = self._prune(next_states)

        qualified = [
            state
            for state in states
            if state.odds >= self.TARGET_ODDS and len(state.days) >= min_days
        ]
        if not qualified:
            return None

        best = max(qualified, key=self._score)
        return Ticket(
            strategy="weekly_safe",
            target_odds=self.TARGET_ODDS,
            actual_odds=best.odds.quantize(Decimal("0.01")),
            selections=best.selections,
        )

    @staticmethod
    def _prepare(
        predictions: list[Prediction],
        *,
        min_probability: float,
        min_confidence: Confidence,
        candidate_limit_per_day: int,
    ) -> list[Prediction]:
        confidence_rank = {
            Confidence.LOW: 0,
            Confidence.MEDIUM: 1,
            Confidence.HIGH: 2,
            Confidence.VERY_HIGH: 3,
        }

        candidates = [
            item
            for item in predictions
            if item.probability >= min_probability
            and confidence_rank[item.confidence] >= confidence_rank[min_confidence]
            and item.odds > Decimal("1")
        ]

        grouped: dict[date, list[Prediction]] = {}
        for item in candidates:
            grouped.setdefault(item.start_time.date(), []).append(item)

        result: list[Prediction] = []
        for day in sorted(grouped):
            event_best: dict[str, Prediction] = {}
            for item in grouped[day]:
                current = event_best.get(item.event_id)
                if current is None or WeeklySafeGenerator._candidate_score(item) > WeeklySafeGenerator._candidate_score(current):
                    event_best[item.event_id] = item

            day_candidates = sorted(
                event_best.values(),
                key=WeeklySafeGenerator._candidate_score,
                reverse=True,
            )
            result.extend(day_candidates[: max(1, candidate_limit_per_day)])

        return result

    @staticmethod
    def _candidate_score(item: Prediction) -> float:
        return item.probability + (item.expected_value * 0.01)

    @staticmethod
    def _score(state: _State) -> float:
        average_probability = state.probability_sum / len(state.selections)
        return average_probability + (len(state.days) * 0.01)
    
    @staticmethod
    def _prune(states: list[_State]) -> list[_State]:
        deduped: dict[tuple[frozenset[str], frozenset[date]], _State] = {}
        for state in states:
            key = (state.event_ids, state.days)
            current = deduped.get(key)
            if current is None or WeeklySafeGenerator._score(state) > WeeklySafeGenerator._score(current):
                deduped[key] = state

        ranked = sorted(
            deduped.values(),
            key=lambda item: (
                len(item.days),
                item.odds,
                WeeklySafeGenerator._score(item),
            ),
            reverse=True,
        )
        return ranked[: WeeklySafeGenerator.BEAM_WIDTH]
