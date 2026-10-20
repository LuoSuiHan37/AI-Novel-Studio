"""Persist automatic writing, publishing and schedule state."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_automation_pipeline"
down_revision: Union[str, Sequence[str], None] = "0006_story_memory_dedupe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = sa.Uuid(as_uuid=True)
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "automation_tasks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("chapter_number", sa.Integer()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", TZ), sa.Column("completed_at", TZ), sa.Column("next_run_at", TZ),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_automation_tasks_project_id", "automation_tasks", ["project_id"])
    op.create_index("ix_automation_tasks_status", "automation_tasks", ["status"])
    op.create_table(
        "publish_tasks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("external_chapter_id", sa.String(255)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text()), sa.Column("published_at", TZ),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("chapter_id", "platform", name="uq_publish_tasks_chapter_platform"),
    )
    op.create_index("ix_publish_tasks_project_id", "publish_tasks", ["project_id"])
    op.create_index("ix_publish_tasks_chapter_id", "publish_tasks", ["chapter_id"])
    op.create_index("ix_publish_tasks_status", "publish_tasks", ["status"])
    op.create_table(
        "automation_schedules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("platforms", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("next_run_at", TZ), sa.Column("last_error", sa.Text()),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_automation_schedules_project"),
    )
    op.create_table(
        "automation_notifications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", UUID, sa.ForeignKey("automation_tasks.id", ondelete="SET NULL")),
        sa.Column("level", sa.String(16), nullable=False, server_default="error"),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("read_at", TZ),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_automation_notifications_project_id", "automation_notifications", ["project_id"])
    op.create_index("ix_automation_notifications_task_id", "automation_notifications", ["task_id"])


def downgrade() -> None:
    op.drop_table("automation_notifications")
    op.drop_table("automation_schedules")
    op.drop_table("publish_tasks")
    op.drop_table("automation_tasks")
