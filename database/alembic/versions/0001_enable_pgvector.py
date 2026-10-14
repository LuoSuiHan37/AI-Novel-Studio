"""Enable pgvector.

Revision ID: 0001_enable_pgvector
Revises:
Create Date: 2026-10-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_enable_pgvector"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
