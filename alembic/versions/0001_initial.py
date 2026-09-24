"""Create initial selection and ticket history tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "selection_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "selections",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("home_team", sa.String(length=255), nullable=False),
        sa.Column("away_team", sa.String(length=255), nullable=False),
        sa.Column("market", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=128), nullable=False),
        sa.Column("specifier", sa.String(length=255), nullable=True),
        sa.Column("outcome_id", sa.String(length=128), nullable=False),
        sa.Column("selection", sa.String(length=255), nullable=False),
        sa.Column("odds", sa.Numeric(12, 4), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["selection_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "id", name="pk_selection_session_id"),
        sa.UniqueConstraint("session_id", "event_id", name="uq_selection_session_event"),
    )
    op.create_index("ix_selections_session_id", "selections", ["session_id"])
    op.create_index("ix_selections_event_id", "selections", ["event_id"])
    op.create_table(
        "ticket_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("combined_odds", sa.Numeric(18, 4), nullable=False),
        sa.Column("selection_count", sa.Integer(), nullable=False),
        sa.Column("provider_response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["selection_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_history_session_id", "ticket_history", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_history_session_id", table_name="ticket_history")
    op.drop_table("ticket_history")
    op.drop_index("ix_selections_event_id", table_name="selections")
    op.drop_index("ix_selections_session_id", table_name="selections")
    op.drop_table("selections")
    op.drop_table("selection_sessions")
