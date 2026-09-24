from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.domain.markets import Market

router = APIRouter(prefix="/meta", tags=["meta"])


class MarketMeta(BaseModel):
    id: Market
    label: str


class StrategyMeta(BaseModel):
    id: str
    label: str
    target_odds: str | None
    description: str


class AppMetaResponse(BaseModel):
    app_name: str
    api_version: str
    markets: list[MarketMeta]
    strategies: list[StrategyMeta]


MARKET_LABELS = {
    Market.OVER_1_5: "Over 1.5",
    Market.OVER_2_5: "Over 2.5",
    Market.BTTS: "Both Teams To Score",
    Market.UNDER_2_5: "Under 2.5",
    Market.UNDER_4_5: "Under 4.5",
}


@router.get("", response_model=AppMetaResponse)
async def get_app_meta() -> AppMetaResponse:
    settings = get_settings()
    return AppMetaResponse(
        app_name=settings.app_name,
        api_version=settings.api_prefix.rsplit("/", 1)[-1],
        markets=[
            MarketMeta(id=market, label=MARKET_LABELS[market])
            for market in Market
        ],
        strategies=[
            StrategyMeta(
                id="custom",
                label="Build ticket",
                target_odds=None,
                description="Build a ticket to any target odds using Over 2.5, BTTS, Under 2.5 and Under 4.5.",
            ),
        ]
    )
