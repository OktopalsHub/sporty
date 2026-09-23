from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ProviderOutcome:
    id: str
    description: str
    odds: Decimal
    active: bool


@dataclass(frozen=True)
class ProviderMarket:
    id: str
    description: str
    specifier: str | None
    active: bool
    outcomes: tuple[ProviderOutcome, ...]


@dataclass(frozen=True)
class ProviderEvent:
    id: str
    tournament_id: str | None
    tournament_name: str | None
    home_team: str
    away_team: str
    start_time: datetime
    status: str
    markets: tuple[ProviderMarket, ...]
