"""Persist human-readable progress for generation and publication tasks."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0014_task_progress_tracking"
down_revision = "0013_schedule_next_run_timezone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_default = sa.text("'[]'::jsonb")
    for table in ("automation_tasks", "publish_tasks"):
        op.add_column(table, sa.Column("current_stage", sa.String(length=64), nullable=False, server_default="queued" if table == "automation_tasks" else "waiting_upload"))
        op.add_column(table, sa.Column("progress_message", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("stage_history", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=json_default))
        op.add_column(table, sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("publish_tasks", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("publish_tasks", "started_at")
    for table in ("publish_tasks", "automation_tasks"):
        op.drop_column(table, "finished_at")
        op.drop_column(table, "heartbeat_at")
        op.drop_column(table, "stage_history")
        op.drop_column(table, "progress_message")
        op.drop_column(table, "current_stage")
