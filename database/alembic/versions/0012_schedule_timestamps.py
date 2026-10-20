"""Ensure schedule rows always receive timestamps."""

from alembic import op
import sqlalchemy as sa


revision = "0012_schedule_timestamps"
down_revision = "0011_fixed_automation_interval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "automation_schedules",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )
    op.alter_column(
        "automation_schedules",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )


def downgrade() -> None:
    op.alter_column(
        "automation_schedules",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
    )
    op.alter_column(
        "automation_schedules",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
    )
