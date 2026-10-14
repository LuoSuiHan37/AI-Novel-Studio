"""Story memory epistemic fields, chapter memory columns, timeline location.

Revision ID: 0004_story_memory
Revises: 0003_domain_fields
Create Date: 2026-10-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_story_memory"
down_revision: Union[str, Sequence[str], None] = "0003_domain_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "story_memories",
        sa.Column("layer", sa.String(16), nullable=False, server_default="chapter"),
    )
    op.add_column(
        "story_memories",
        sa.Column(
            "epistemic_status",
            sa.String(32),
            nullable=False,
            server_default="tentative_fact",
        ),
    )
    op.add_column("story_memories", sa.Column("chapter_number", sa.Integer(), nullable=True))
    op.add_column("story_memories", sa.Column("location", sa.String(255), nullable=True))
    op.add_column(
        "story_memories",
        sa.Column("known_by", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "story_memories",
        sa.Column("unknown_to", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "story_memories",
        sa.Column("tags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_index("ix_story_memories_layer", "story_memories", ["layer"])
    op.create_index("ix_story_memories_epistemic_status", "story_memories", ["epistemic_status"])

    op.add_column("timeline_events", sa.Column("location", sa.String(255), nullable=True))

    op.add_column(
        "chapter_summaries",
        sa.Column("new_facts", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "chapter_summaries",
        sa.Column(
            "character_changes",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "chapter_summaries",
        sa.Column("new_secrets", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "chapter_summaries",
        sa.Column(
            "resolved_secrets",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "chapter_summaries",
        sa.Column(
            "unresolved_hooks",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("chapter_summaries", sa.Column("location", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("chapter_summaries", "location")
    op.drop_column("chapter_summaries", "unresolved_hooks")
    op.drop_column("chapter_summaries", "resolved_secrets")
    op.drop_column("chapter_summaries", "new_secrets")
    op.drop_column("chapter_summaries", "character_changes")
    op.drop_column("chapter_summaries", "new_facts")
    op.drop_column("timeline_events", "location")
    op.drop_index("ix_story_memories_epistemic_status", table_name="story_memories")
    op.drop_index("ix_story_memories_layer", table_name="story_memories")
    op.drop_column("story_memories", "tags")
    op.drop_column("story_memories", "unknown_to")
    op.drop_column("story_memories", "known_by")
    op.drop_column("story_memories", "location")
    op.drop_column("story_memories", "chapter_number")
    op.drop_column("story_memories", "epistemic_status")
    op.drop_column("story_memories", "layer")
