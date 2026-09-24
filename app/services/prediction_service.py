from __future__ import annotations

import hashlib
import re
from decimal import Decimal

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.domain.provider import ProviderEvent, ProviderMarket, ProviderOutcome

MARKET_ALIASES: dict[Market, tuple[str, ...]] = {
    Market.OVER_2_5: ("over 2.5", "over2.5", "over 2.5 goals"),
    Market.BTTS: ("both teams to score", "btts", "gg", "yes"),
    Market.UNDER_2_5: ("under 2.5", "under2.5", "under 2.5 goals"),
    Market.UNDER_4_5: ("under 4.5", "under4.5", "under 4.5 goals"),
}


class PredictionService:
    """Converts normalized provider markets into validated prediction candidates.

    This phase deliberately uses provider odds as the baseline signal. The
    Gemini/model scoring layer comes later and can replace the probability
    scorer without changing the provider or strategy contracts.
    """

    def generate(self, events: list[ProviderEvent], market: Market) -> list[Prediction]:
        predictions: list[Prediction] = []
        for event in events:
            for provider_market in event.markets:
                if not provider_market.active:
                    continue
                predictions.extend(self._from_market(event, provider_market, market))

        return self._deduplicate(predictions)

    def generate_all(self, events: list[ProviderEvent]) -> list[Prediction]:
        predictions: list[Prediction] = []
        for market in Market:
            predictions.extend(self.generate(events, market))
        return self._deduplicate(predictions)

    def _from_market(
        self,
        event: ProviderEvent,
        provider_market: ProviderMarket,
        target: Market,
    ) -> list[Prediction]:
        description = self._normalize(provider_market.description)
        specifier = self._normalize(provider_market.specifier or "")

        if not self._market_matches(description, specifier, target):
            return []

        result: list[Prediction] = []
        for outcome in provider_market.outcomes:
            if not outcome.active or outcome.odds <= Decimal("1.00"):
                continue
            if not self._outcome_matches(outcome, target):
                continue

            probability = self._implied_probability(outcome.odds)
            confidence = self._confidence(probability)
            prediction_id = self._prediction_id(event.id, provider_market.id, outcome.id)

            result.append(
                Prediction(
                    id=prediction_id,
                    event_id=event.id,
                    home_team=event.home_team,
                    away_team=event.away_team,
                    start_time=event.start_time,
                    market=target,
                    market_id=provider_market.id,
                    specifier=provider_market.specifier,
                    outcome_id=outcome.id,
                    selection=outcome.description,
                    odds=outcome.odds,
                    probability=probability,
                    confidence=confidence,
                    reasons=(
                        "Candidate extracted from an active SportyBet market.",
                        f"Implied probability from odds: {probability:.1%}.",
                    ),
                )
            )

        return result

    @staticmethod
    def _market_matches(description: str, specifier: str, target: Market) -> bool:
        aliases = MARKET_ALIASES[target]
        if any(alias in description or alias in specifier for alias in aliases):
            return True

        if description in {"over/under", "over under", "total goals", "total"}:
            line = PredictionService._specifier_value(specifier, "total")
            target_line = {
                Market.OVER_2_5: "2.5",
                Market.UNDER_2_5: "2.5",
                Market.UNDER_4_5: "4.5",
            }.get(target)
            return line == target_line

        if target == Market.BTTS and ("gg/ng" in description or description == "gg"):
            return True

        return False

    @staticmethod
    def _outcome_matches(outcome: ProviderOutcome, target: Market) -> bool:
        value = re.sub(r"[^a-z0-9.]+", " ", outcome.description.lower()).strip()
        if target == Market.OVER_2_5:
            return value == "over" or value.startswith("over ")
        if target in {Market.UNDER_2_5, Market.UNDER_4_5}:
            return value == "under" or value.startswith("under ")
        if target == Market.BTTS:
            return value in {"yes", "gg", "goal goal", "both teams to score", "btts"}
        return True

    @staticmethod
    def _specifier_value(specifier: str, key: str) -> str | None:
        match = re.search(
            rf"(?:^|[;|,])\s*{re.escape(key)}\s*=\s*(-?\d+(?:\.\d+)?)",
            specifier,
        )
        return match.group(1) if match else None

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.lower().strip())

    @staticmethod
    def _implied_probability(odds: Decimal) -> float:
        return min(0.99, max(0.01, 1.0 / float(odds)))

    @staticmethod
    def _confidence(probability: float) -> Confidence:
        if probability >= 0.75:
            return Confidence.VERY_HIGH
        if probability >= 0.65:
            return Confidence.HIGH
        if probability >= 0.55:
            return Confidence.MEDIUM
        return Confidence.LOW

    @staticmethod
    def _prediction_id(event_id: str, market_id: str, outcome_id: str) -> str:
        raw = f"{event_id}:{market_id}:{outcome_id}".encode()
        return hashlib.sha256(raw).hexdigest()[:24]

    @staticmethod
    def _deduplicate(predictions: list[Prediction]) -> list[Prediction]:
        seen: set[tuple[str, str, str]] = set()
        result: list[Prediction] = []
        for prediction in predictions:
            key = (prediction.event_id, prediction.market.value, prediction.outcome_id)
            if key in seen:
                continue
            seen.add(key)
            result.append(prediction)
        return result
