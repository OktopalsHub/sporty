from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import TicketHistoryModel


@dataclass(frozen=True)
class TicketHistory:
    id: str
    session_id: str
    combined_odds: Decimal
    selection_count: int
    provider_response: dict[str, Any]
    created_at: datetime


class TicketHistoryService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        session_id: str,
        combined_odds: Decimal,
        selection_count: int,
        provider_response: dict[str, Any],
    ) -> TicketHistory:
        item = TicketHistoryModel(
            id=str(uuid4()),
            session_id=session_id,
            combined_odds=combined_odds,
            selection_count=selection_count,
            provider_response=provider_response,
            created_at=datetime.now(timezone.utc),
        )
        with self._session_factory() as db:
            db.add(item)
            db.commit()
            db.refresh(item)
            return self._to_history(item)

    def list_for_session(self, session_id: str) -> list[TicketHistory]:
        with self._session_factory() as db:
            items = db.scalars(
                select(TicketHistoryModel)
                .where(TicketHistoryModel.session_id == session_id)
                .order_by(TicketHistoryModel.created_at.desc())
            ).all()
            return [self._to_history(item) for item in items]

    @staticmethod
    def _to_history(item: TicketHistoryModel) -> TicketHistory:
        return TicketHistory(
            id=item.id,
            session_id=item.session_id,
            combined_odds=Decimal(item.combined_odds),
            selection_count=item.selection_count,
            provider_response=item.provider_response,
            created_at=item.created_at,
        )
