from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.providers.gemini.client import GeminiClient
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalysisRequest(BaseModel):
    event_id: str
    home_team: str
    away_team: str
    market: Market
    market_id: str
    specifier: str | None = None
    outcome_id: str
    selection: str
    odds: float = Field(gt=1.0)
    probability: float = Field(ge=0.0, le=1.0)
    confidence: Confidence
    reasons: list[str] = Field(default_factory=list)


@router.post("/predict")
async def analyze_prediction(request: AnalysisRequest) -> dict:
    settings = get_settings()
    gemini = (
        GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            base_url=settings.gemini_base_url,
            timeout=settings.gemini_timeout,
        )
        if settings.gemini_api_key
        else None
    )

    prediction = Prediction(
        id=f"{request.event_id}:{request.market_id}:{request.outcome_id}",
        event_id=request.event_id,
        home_team=request.home_team,
        away_team=request.away_team,
        start_time=datetime.now(timezone.utc),
        market=request.market,
        market_id=request.market_id,
        specifier=request.specifier,
        outcome_id=request.outcome_id,
        selection=request.selection,
        odds=Decimal(str(request.odds)),
        probability=request.probability,
        confidence=request.confidence,
        reasons=tuple(request.reasons),
    )

    try:
        result = await AnalysisService(gemini).analyze(prediction)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Prediction analysis failed") from exc

    return {
        "probability": result.probability,
        "confidence": result.confidence,
        "reasons": list(result.reasons),
        "provider": result.provider,
        "model": result.model,
    }
