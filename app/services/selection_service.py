from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import _engine_kwargs
from app.domain.markets import Market
from app.domain.predictions import Confidence, Prediction
from app.models import SelectionModel, SelectionSessionModel


class SelectionNotFoundError(KeyError):
    pass


class SelectionConflictError(ValueError):
    pass


@dataclass
class SelectionSession:
    id: str
    selections: dict[str, Prediction]


class SelectionService:
    """Persists exact user selections in the database."""

    def __init__(
        self,
        database_url: str | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            from app.config import get_settings

            url = database_url or get_settings().database_url
            db_engine = create_engine(url, future=True, **_engine_kwargs(url))
            self._session_factory = sessionmaker(
                bind=db_engine,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
            )
        self._lock = Lock()

    def create_session(self) -> SelectionSession:
        now = datetime.now(timezone.utc)
        session = SelectionSessionModel(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as db:
            db.add(session)
            db.commit()
            return SelectionSession(id=session.id, selections={})

    def get_session(self, session_id: str) -> SelectionSession:
        with self._session_factory() as db:
            session = db.get(SelectionSessionModel, session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)
            return SelectionSession(
                id=session.id,
                selections={item.id: self._to_prediction(item) for item in session.selections},
            )

    def add(self, session_id: str, prediction: Prediction) -> SelectionSession:
        with self._lock, self._session_factory() as db:
            session = db.get(SelectionSessionModel, session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)

            existing = (
                db.query(SelectionModel)
                .filter(
                    SelectionModel.session_id == session_id,
                    SelectionModel.event_id == prediction.event_id,
                    SelectionModel.id != prediction.id,
                )
                .first()
            )
            if existing is not None:
                raise SelectionConflictError(
                    f"Event {prediction.event_id} already has selection {existing.id}"
                )

            item = db.get(SelectionModel, prediction.id)
            now = datetime.now(timezone.utc)
            if item is None:
                db.add(self._to_model(session_id, prediction, now))
            elif item.session_id != session_id:
                raise SelectionConflictError(
                    f"Selection {prediction.id} already belongs to another session"
                )
            else:
                item.updated_at = now

            session.updated_at = now
            db.commit()
            return self.get_session(session_id)

    def remove(self, session_id: str, prediction_id: str) -> SelectionSession:
        with self._lock, self._session_factory() as db:
            session = db.get(SelectionSessionModel, session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)

            item = db.get(SelectionModel, prediction_id)
            if item is None or item.session_id != session_id:
                raise SelectionNotFoundError(prediction_id)

            db.delete(item)
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            return self.get_session(session_id)

    def clear(self, session_id: str) -> SelectionSession:
        with self._lock, self._session_factory() as db:
            session = db.get(SelectionSessionModel, session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)

            db.query(SelectionModel).filter(
                SelectionModel.session_id == session_id
            ).delete(synchronize_session=False)
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            return SelectionSession(id=session_id, selections={})

    def delete_session(self, session_id: str) -> None:
        with self._lock, self._session_factory() as db:
            session = db.get(SelectionSessionModel, session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)
            db.delete(session)
            db.commit()

    @staticmethod
    def _to_model(session_id: str, prediction: Prediction, now: datetime) -> SelectionModel:
        return SelectionModel(
            id=prediction.id,
            session_id=session_id,
            event_id=prediction.event_id,
            start_time=prediction.start_time,
            home_team=prediction.home_team,
            away_team=prediction.away_team,
            market=prediction.market.value,
            market_id=prediction.market_id,
            specifier=prediction.specifier,
            outcome_id=prediction.outcome_id,
            selection=prediction.selection,
            odds=prediction.odds,
            probability=prediction.probability,
            confidence=prediction.confidence.value,
            reasons=list(prediction.reasons),
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _to_prediction(item: SelectionModel) -> Prediction:
        return Prediction(
            id=item.id,
            event_id=item.event_id,
            home_team=item.home_team,
            away_team=item.away_team,
            start_time=item.start_time,
            market=Market(item.market),
            market_id=item.market_id,
            specifier=item.specifier,
            outcome_id=item.outcome_id,
            selection=item.selection,
            odds=Decimal(item.odds),
            probability=item.probability,
            confidence=Confidence(item.confidence),
            reasons=tuple(item.reasons or ()),
        )
