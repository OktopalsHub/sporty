"""Add background prediction jobs."""

from alembic import op
import sqlalchemy as sa

revision = "0002_prediction_jobs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prediction_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prediction_jobs_job_type", "prediction_jobs", ["job_type"])
    op.create_index("ix_prediction_jobs_status", "prediction_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_prediction_jobs_status", table_name="prediction_jobs")
    op.drop_index("ix_prediction_jobs_job_type", table_name="prediction_jobs")
    op.drop_table("prediction_jobs")
