"""Ensure each chapter has one durable summary.

Revision ID: 0005_unique_chapter_summary
Revises: 0004_story_memory
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0005_unique_chapter_summary"
down_revision: Union[str, Sequence[str], None] = "0004_story_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the newest summary when upgrading databases created before the
    # idempotent backfill contract existed.
    op.execute(
        """
        DELETE FROM chapter_summaries older
        USING chapter_summaries newer
        WHERE older.chapter_id = newer.chapter_id
          AND (older.updated_at, older.id) < (newer.updated_at, newer.id)
        """
    )
    op.create_unique_constraint(
        "uq_chapter_summaries_chapter_id",
        "chapter_summaries",
        ["chapter_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_chapter_summaries_chapter_id",
        "chapter_summaries",
        type_="unique",
    )
