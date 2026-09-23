from __future__ import annotations

from app.domain.markets import Market
from app.domain.predictions import Prediction
from app.providers.sportybet.client import SportyBetClient
from app.services.five_k_generator import FiveKGenerator
from app.services.market_generator import MarketGenerator
from app.services.one_k_generator import OneKGenerator
from app.services.prediction_service import PredictionService
from app.services.weekly_safe_generator import WeeklySafeGenerator


SUPPORTED_JOB_TYPES = {
    "1k",
    "5k",
    "weekly_safe",
    "over_1_5",
    "over_2_5",
    "btts",
    "under_2_5",
    "under_4_5",
}


async def execute_prediction_job(job_type: str, payload: dict) -> dict:
    if job_type not in SUPPORTED_JOB_TYPES:
        raise ValueError(f"Unsupported job type: {job_type}")

    client = SportyBetClient()
    service = PredictionService()
    events, _ = await client.get_upcoming_events(
        page=payload.get("page", 1),
        page_size=payload.get("page_size", 100),
        hours=payload.get("hours", 168),
    )

    if job_type in {"1k", "5k", "weekly_safe"}:
        predictions: list[Prediction] = []
        for market in Market:
            predictions.extend(service.generate(events, market))
        predictions = [
            item for item in predictions
            if item.probability >= payload.get(
                "min_probability",
                0.55 if job_type == "5k" else 0.0,
            )
        ]
        if job_type == "1k":
            ticket = OneKGenerator().generate(predictions)
        elif job_type == "5k":
            ticket = FiveKGenerator().generate(
                predictions,
                min_probability=payload.get("min_probability", 0.55),
                candidate_pool_size=payload.get("candidate_pool_size", 150),
                attempts=payload.get("attempts", 25),
            )
        else:
            from app.domain.predictions import Confidence
            ticket = WeeklySafeGenerator().generate(
                predictions,
                min_probability=payload.get("min_probability", 0.75),
                min_confidence=Confidence(payload.get("min_confidence", "high")),
                min_days=payload.get("min_days", 3),
                candidate_limit_per_day=payload.get("candidate_limit_per_day", 40),
            )
        if ticket is None:
            raise ValueError("No qualifying ticket could be generated.")
        return {
            "strategy": ticket.strategy,
            "target_odds": str(ticket.target_odds),
            "actual_odds": str(ticket.actual_odds),
            "selection_count": len(ticket.selections),
            "selections": [_serialize_prediction(item) for item in ticket.selections],
        }

    market_map = {
        "over_1_5": Market.OVER_1_5,
        "over_2_5": Market.OVER_2_5,
        "btts": Market.BTTS,
        "under_2_5": Market.UNDER_2_5,
        "under_4_5": Market.UNDER_4_5,
    }
    market = market_map[job_type]
    predictions = service.generate(events, market)
    result = MarketGenerator().generate(
        predictions,
        market,
        min_probability=payload.get("min_probability", 0.0),
        confidence=None,
    )
    return {
        "market": result.market,
        "total_candidates": result.total_candidates,
        "predictions": [_serialize_prediction(item) for item in result.predictions],
    }


def _serialize_prediction(item: Prediction) -> dict:
    return {
        "id": item.id,
        "event_id": item.event_id,
        "home_team": item.home_team,
        "away_team": item.away_team,
        "start_time": item.start_time.isoformat(),
        "market": item.market,
        "market_id": item.market_id,
        "specifier": item.specifier,
        "outcome_id": item.outcome_id,
        "selection": item.selection,
        "odds": str(item.odds),
        "probability": item.probability,
        "confidence": item.confidence,
        "reasons": list(item.reasons),
    }
