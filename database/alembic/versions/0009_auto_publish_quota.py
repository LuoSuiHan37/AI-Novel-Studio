"""Add automatic formal publishing switch and daily quota state."""

from alembic import op
import sqlalchemy as sa


revision = "0009_auto_publish_quota"
down_revision = "0008_platform_chapter_mapping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("novel_projects", sa.Column("auto_publish_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("novel_projects", sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "automation_daily_quotas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("quota_date", sa.Date(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("published_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "platform", "quota_date", name="uq_automation_daily_quota"),
    )
    op.create_index("ix_automation_daily_quotas_project_id", "automation_daily_quotas", ["project_id"])
    op.create_index("ix_automation_daily_quotas_quota_date", "automation_daily_quotas", ["quota_date"])


def downgrade() -> None:
    op.drop_index("ix_automation_daily_quotas_quota_date", table_name="automation_daily_quotas")
    op.drop_index("ix_automation_daily_quotas_project_id", table_name="automation_daily_quotas")
    op.drop_table("automation_daily_quotas")
    op.drop_column("novel_projects", "completed")
    op.drop_column("novel_projects", "auto_publish_enabled")
