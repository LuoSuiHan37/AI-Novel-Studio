"""Use timezone-aware timestamps for persisted automation task state."""

from alembic import op
import sqlalchemy as sa


revision = "0015_task_timestamps_tz"
down_revision = "0014_task_progress_tracking"
branch_labels = None
depends_on = None


def _alter(table: str, column: str) -> None:
    op.alter_column(
        table,
        column,
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def upgrade() -> None:
    for table, columns in {
        "automation_tasks": ("started_at", "completed_at", "next_run_at"),
        "publish_tasks": ("published_at",),
    }.items():
        for column in columns:
            _alter(table, column)


def downgrade() -> None:
    for table, columns in {
        "automation_tasks": ("started_at", "completed_at", "next_run_at"),
        "publish_tasks": ("published_at",),
    }.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                existing_type=sa.DateTime(timezone=True),
                type_=sa.DateTime(timezone=False),
                postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            )
