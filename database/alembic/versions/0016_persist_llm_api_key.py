"""Persist the local LLM credential needed by background workers."""

from alembic import op
import sqlalchemy as sa


revision = "0016_persist_llm_api_key"
down_revision = "0015_task_timestamps_tz"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_configs", sa.Column("api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_configs", "api_key")
