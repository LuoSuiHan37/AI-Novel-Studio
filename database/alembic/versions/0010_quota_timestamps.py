"""Default timestamps for daily quota rows."""

from alembic import op
import sqlalchemy as sa


revision = "0010_quota_timestamps"
down_revision = "0009_auto_publish_quota"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "automation_daily_quotas",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )
    op.alter_column(
        "automation_daily_quotas",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )


def downgrade() -> None:
    op.alter_column(
        "automation_daily_quotas",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
    )
    op.alter_column(
        "automation_daily_quotas",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
    )
