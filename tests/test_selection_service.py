from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.services.selection_service import SelectionConflictError, SelectionService


@pytest.fixture
def selection_service(tmp_path):
    return SelectionService(database_url=f"sqlite:///{tmp_path / 'sporty.db'}")


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


def test_add_and_remove_exact_selection(selection_service):
    service = selection_service
    session = service.create_session()
    item = prediction(1)

    service.add(session.id, item)
    assert service.get_session(session.id).selections[item.id] == item

    service.remove(session.id, item.id)
    assert service.get_session(session.id).selections == {}


def test_same_event_cannot_have_two_selections(selection_service):
    service = selection_service
    session = service.create_session()
    service.add(session.id, prediction(1, "event-1"))

    with pytest.raises(SelectionConflictError):
        service.add(session.id, prediction(2, "event-1"))


def test_same_prediction_id_is_idempotent(selection_service):
    service = selection_service
    session = service.create_session()
    item = prediction(1)

    service.add(session.id, item)
    service.add(session.id, item)

    assert list(service.get_session(session.id).selections) == [item.id]


def test_clear_removes_all_selections(selection_service):
    service = selection_service
    session = service.create_session()
    service.add(session.id, prediction(1))
    service.add(session.id, prediction(2))

    service.clear(session.id)
    assert service.get_session(session.id).selections == {}


def test_selection_persists_across_service_instances(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'sporty.db'}"
    first = SelectionService(database_url=database_url)
    session = first.create_session()
    item = prediction(1)

    first.add(session.id, item)

    second = SelectionService(database_url=database_url)
    restored = second.get_session(session.id)

    assert restored.selections[item.id] == item


def test_same_prediction_can_be_selected_in_different_sessions(tmp_path):
    service = SelectionService(database_url=f"sqlite:///{tmp_path / 'sporty.db'}")
    first = service.create_session()
    second = service.create_session()
    item = prediction(1)

    service.add(first.id, item)
    service.add(second.id, item)

    assert list(service.get_session(first.id).selections) == [item.id]
    assert list(service.get_session(second.id).selections) == [item.id]
