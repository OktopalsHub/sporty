from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.services.selection_service import SelectionConflictError, SelectionService


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


def test_add_and_remove_exact_selection():
    service = SelectionService()
    session = service.create_session()
    item = prediction(1)

    service.add(session.id, item)

    assert service.get_session(session.id).selections[item.id] == item

    service.remove(session.id, item.id)

    assert service.get_session(session.id).selections == {}


def test_same_event_cannot_have_two_selections():
    service = SelectionService()
    session = service.create_session()

    service.add(session.id, prediction(1, "event-1"))

    with pytest.raises(SelectionConflictError):
        service.add(session.id, prediction(2, "event-1"))


def test_same_prediction_id_is_idempotent():
    service = SelectionService()
    session = service.create_session()
    item = prediction(1)

    service.add(session.id, item)
    service.add(session.id, item)

    assert list(service.get_session(session.id).selections) == [item.id]


def test_clear_removes_all_selections():
    service = SelectionService()
    session = service.create_session()
    service.add(session.id, prediction(1))
    service.add(session.id, prediction(2))

    service.clear(session.id)

    assert service.get_session(session.id).selections == {}
