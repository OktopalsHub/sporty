from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from app.domain.predictions import Prediction


class SelectionNotFoundError(KeyError):
    pass


class SelectionConflictError(ValueError):
    pass


@dataclass
class SelectionSession:
    id: str
    selections: dict[str, Prediction]


class SelectionService:
    """Stores the exact predictions selected by a user for the current session.

    Persistence is intentionally deferred to the database phase. Until then,
    selections live in process memory and are lost when the API restarts.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SelectionSession] = {}
        self._lock = Lock()

    def create_session(self) -> SelectionSession:
        session = SelectionSession(id=str(uuid4()), selections={})
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> SelectionSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)
            return session

    def add(self, session_id: str, prediction: Prediction) -> SelectionSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)

            existing = next(
                (
                    item
                    for item in session.selections.values()
                    if item.event_id == prediction.event_id and item.id != prediction.id
                ),
                None,
            )
            if existing is not None:
                raise SelectionConflictError(
                    f"Event {prediction.event_id} already has selection {existing.id}"
                )

            session.selections[prediction.id] = prediction
            return session

    def remove(self, session_id: str, prediction_id: str) -> SelectionSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)
            if prediction_id not in session.selections:
                raise SelectionNotFoundError(prediction_id)

            del session.selections[prediction_id]
            return session

    def clear(self, session_id: str) -> SelectionSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SelectionNotFoundError(session_id)
            session.selections.clear()
            return session

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            if session_id not in self._sessions:
                raise SelectionNotFoundError(session_id)
            del self._sessions[session_id]
