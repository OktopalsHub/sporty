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
                id="1k",
                label="1K Odds",
                target_odds="1000",
                description="Build an accumulator targeting at least 1,000 combined odds.",
            ),
            StrategyMeta(
                id="5k_random",
                label="5K Random",
                target_odds="5000",
                description="Build a randomized accumulator targeting at least 5,000 combined odds.",
            ),
            StrategyMeta(
                id="weekly_safe",
                label="Weekly Safe",
                target_odds="10000",
                description="Build a weekly high-confidence accumulator targeting at least 10,000 combined odds.",
            ),
        ],
    )
