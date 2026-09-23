from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.db import Base, _engine_kwargs

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.domain.provider import ProviderEvent, ProviderMarket, ProviderOutcome
from app.providers.sportybet.client import SportyBetError
from app.services.selection_service import SelectionService
from app.services.ticket_builder import TicketBuildError, TicketBuilder


def prediction(index: int, event_id: str | None = None) -> Prediction:
    return Prediction(
        id=f"prediction-{index}",
        event_id=event_id or f"event-{index}",
        home_team=f"Home {index}",
        away_team=f"Away {index}",
        start_time=datetime.now(timezone.utc),
        market=Market.OVER_1_5,
        market_id="18",
        specifier="total=1.5",
        outcome_id=str(index),
        selection="Over 1.5",
        odds=Decimal("1.50"),
        probability=0.80,
        confidence=Confidence.HIGH,
    )


@pytest.fixture
def selection_service(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'sporty.db'}"
    engine = create_engine(database_url, future=True, **_engine_kwargs(database_url))
    Base.metadata.create_all(bind=engine)
    return SelectionService(session_factory=sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))


class FakeProvider:
    def __init__(self, event: ProviderEvent | None = None) -> None:
        self.event = event
        self.sent: list[dict[str, str | None]] | None = None

    async def get_event_markets(self, event_id: str) -> ProviderEvent:
        if self.event is None:
            raise SportyBetError("missing event")
        return self.event

    async def create_booking(self, selections: list[dict[str, str | None]]) -> dict:
        self.sent = selections
        return {"data": {"shareCode": "ABC123"}}


def provider_event(event_id: str = "event-1", outcome_id: str = "1") -> ProviderEvent:
    return ProviderEvent(
        id=event_id,
        tournament_id="tournament-1",
        tournament_name="Test League",
        home_team="Home 1",
        away_team="Away 1",
        start_time=datetime.now(timezone.utc),
        status="not_started",
        markets=(
            ProviderMarket(
                id="18",
                description="Over/Under 1.5",
                specifier="total=1.5",
                active=True,
                outcomes=(
                    ProviderOutcome(
                        id=outcome_id,
                        description="Over 1.5",
                        odds=Decimal("1.75"),
                        active=True,
                    ),
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_build_sends_exact_selected_provider_ids(selection_service) -> None:
    selections = selection_service
    session = selections.create_session()
    selected = prediction(1)
    selections.add(session.id, selected)
    provider = FakeProvider(provider_event())
    builder = TicketBuilder(selections, provider)

    result = await builder.build(session.id)

    assert len(result.selections) == 1
    assert result.selections[0].id == selected.id
    assert result.selections[0].odds == Decimal("1.50")
    assert provider.sent == [
        {
            "event_id": "event-1",
            "market_id": "18",
            "specifier": "total=1.5",
            "outcome_id": "1",
        }
    ]
    assert result.provider_response["data"]["shareCode"] == "ABC123"


@pytest.mark.asyncio
async def test_empty_selection_session_is_rejected(selection_service) -> None:
    selections = selection_service
    session = selections.create_session()
    builder = TicketBuilder(selections, FakeProvider())

    with pytest.raises(TicketBuildError, match="empty"):
        await builder.build(session.id)


@pytest.mark.asyncio
async def test_unavailable_selected_outcome_is_rejected(selection_service) -> None:
    selections = selection_service
    session = selections.create_session()
    selections.add(session.id, prediction(1))
    provider = FakeProvider(provider_event(outcome_id="different"))
    builder = TicketBuilder(selections, provider)

    with pytest.raises(TicketBuildError, match="outcome"):
        await builder.build(session.id)


@pytest.mark.asyncio
async def test_provider_failure_is_rejected_without_booking(selection_service) -> None:
    selections = selection_service
    session = selections.create_session()
    selections.add(session.id, prediction(1))
    provider = FakeProvider()
    builder = TicketBuilder(selections, provider)

    with pytest.raises(TicketBuildError, match="no longer available"):
        await builder.build(session.id)
    assert provider.sent is None
