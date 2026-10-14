"""Add database-level idempotency keys for generated story memory."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006_story_memory_dedupe"
down_revision: Union[str, Sequence[str], None] = "0005_unique_chapter_summary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("story_memories", sa.Column("dedupe_key", sa.String(255), nullable=True))
    op.execute(
        """
        UPDATE story_memories
        SET dedupe_key = CASE
            WHEN extra_metadata->>'kind' = 'chapter_memory'
                THEN 'chapter_memory:' || source_chapter_id::text
            WHEN extra_metadata->>'kind' = 'character_state'
                THEN 'character_state:' || source_chapter_id::text || ':' || COALESCE(extra_metadata->>'name', '')
            WHEN extra_metadata->>'kind' IN ('fact', 'knowledge_boundary')
                THEN (extra_metadata->>'kind') || ':' || source_chapter_id::text || ':' || md5(content)
            WHEN extra_metadata->>'kind' = 'style_ledger'
                THEN 'style_ledger:' || project_id::text
            ELSE NULL
        END
        WHERE extra_metadata ? 'kind'
        """
    )
    op.execute(
        """
        DELETE FROM story_memories older
        USING story_memories newer
        WHERE older.project_id = newer.project_id
          AND older.dedupe_key IS NOT NULL
          AND older.dedupe_key = newer.dedupe_key
          AND (older.updated_at, older.id) < (newer.updated_at, newer.id)
        """
    )
    op.create_unique_constraint(
        "uq_story_memories_project_dedupe_key",
        "story_memories",
        ["project_id", "dedupe_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_story_memories_project_dedupe_key", "story_memories", type_="unique")
    op.drop_column("story_memories", "dedupe_key")
