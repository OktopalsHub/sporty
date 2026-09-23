from decimal import Decimal

from app.db import create_database_engine
from app.models import Base
from app.services.ticket_history_service import TicketHistoryService
from sqlalchemy.orm import sessionmaker


def test_ticket_history_persists_and_lists(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'sporty.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    service = TicketHistoryService(factory)

    service.record(
        session_id="session-1",
        combined_odds=Decimal("1234.56"),
        selection_count=8,
        provider_response={"data": {"shareCode": "ABC123"}},
    )

    history = service.list_for_session("session-1")

    assert len(history) == 1
    assert history[0].combined_odds == Decimal("1234.5600")
    assert history[0].selection_count == 8
    assert history[0].provider_response["data"]["shareCode"] == "ABC123"
