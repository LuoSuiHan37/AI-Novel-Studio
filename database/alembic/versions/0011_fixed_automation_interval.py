"""Fix automatic serialization cadence to twenty minutes."""

from alembic import op
import sqlalchemy as sa


revision = "0011_fixed_automation_interval"
down_revision = "0010_quota_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE automation_schedules SET interval_minutes = 20")
    op.alter_column(
        "automation_schedules",
        "interval_minutes",
        existing_type=sa.Integer(),
        server_default="20",
    )


def downgrade() -> None:
    op.alter_column(
        "automation_schedules",
        "interval_minutes",
        existing_type=sa.Integer(),
        server_default="1440",
    )
