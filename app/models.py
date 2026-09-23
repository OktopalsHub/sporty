from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SelectionSessionModel(Base):
    __tablename__ = "selection_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    selections: Mapped[list["SelectionModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SelectionModel.created_at",
    )
    ticket_history: Mapped[list["TicketHistoryModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TicketHistoryModel.created_at.desc()",
    )


class SelectionModel(Base):
    __tablename__ = "selections"
    __table_args__ = (
        UniqueConstraint("session_id", "id", name="pk_selection_session_id"),
        UniqueConstraint("session_id", "event_id", name="uq_selection_session_event"),
    )

    id: Mapped[str] = mapped_column(String(64))
    session_id: Mapped[str] = mapped_column(
        ForeignKey("selection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    home_team: Mapped[str] = mapped_column(String(255), nullable=False)
    away_team: Mapped[str] = mapped_column(String(255), nullable=False)
    market: Mapped[str] = mapped_column(String(64), nullable=False)
    market_id: Mapped[str] = mapped_column(String(128), nullable=False)
    specifier: Mapped[str | None] = mapped_column(String(255))
    outcome_id: Mapped[str] = mapped_column(String(128), nullable=False)
    selection: Mapped[str] = mapped_column(String(255), nullable=False)
    odds: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    probability: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[SelectionSessionModel] = relationship(back_populates="selections")


class TicketHistoryModel(Base):
    __tablename__ = "ticket_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("selection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    combined_odds: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    selection_count: Mapped[int] = mapped_column(nullable=False)
    provider_response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[SelectionSessionModel] = relationship(back_populates="ticket_history")
