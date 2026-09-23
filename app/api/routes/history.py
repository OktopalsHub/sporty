from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import SessionLocal
from app.services.ticket_history_service import TicketHistoryService

router = APIRouter(prefix="/history", tags=["history"])
history_service = TicketHistoryService(SessionLocal)


class TicketHistoryResponse(BaseModel):
    id: str
    session_id: str
    combined_odds: str
    selection_count: int
    provider_response: dict
    created_at: datetime


@router.get("/tickets/{session_id}", response_model=list[TicketHistoryResponse])
async def get_ticket_history(session_id: str) -> list[TicketHistoryResponse]:
    return [
        TicketHistoryResponse(
            id=item.id,
            session_id=item.session_id,
            combined_odds=str(item.combined_odds),
            selection_count=item.selection_count,
            provider_response=item.provider_response,
            created_at=item.created_at,
        )
        for item in history_service.list_for_session(session_id)
    ]
