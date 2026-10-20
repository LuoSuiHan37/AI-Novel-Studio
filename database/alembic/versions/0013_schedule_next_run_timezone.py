"""Store schedule next-run timestamps with timezone information."""

from alembic import op
import sqlalchemy as sa


revision = "0013_schedule_next_run_timezone"
down_revision = "0012_schedule_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "automation_schedules",
        "next_run_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        postgresql_using="next_run_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "automation_schedules",
        "next_run_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        postgresql_using="next_run_at AT TIME ZONE 'UTC'",
    )
