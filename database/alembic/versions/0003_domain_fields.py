"""Domain fields for story bible, character, and plans.

Revision ID: 0003_domain_fields
Revises: 0002_core_schema
Create Date: 2026-10-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_domain_fields"
down_revision: Union[str, Sequence[str], None] = "0002_core_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("story_bibles", sa.Column("narrative_style", sa.Text(), nullable=True))
    op.add_column("story_bibles", sa.Column("pov", sa.String(32), nullable=True))
    op.add_column("story_bibles", sa.Column("tense", sa.String(16), nullable=True))
    op.add_column("story_bibles", sa.Column("target_word_count", sa.Integer(), nullable=True))
    op.add_column("story_bibles", sa.Column("chapter_word_count", sa.Integer(), nullable=True))
    op.add_column("story_bibles", sa.Column("romance_level", sa.String(16), nullable=True))
    op.add_column("story_bibles", sa.Column("violence_level", sa.String(16), nullable=True))
    op.add_column("story_bibles", sa.Column("heat_level", sa.String(16), nullable=True))

    op.add_column("characters", sa.Column("background", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("goal", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("motivation", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("fear", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("secret", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("strength", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("weakness", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("internal_conflict", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("external_conflict", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("speech_style", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("character_arc", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("status", sa.String(32), nullable=False, server_default="draft"))

    op.add_column("chapter_plans", sa.Column("chapter_number", sa.Integer(), nullable=True))
    op.add_column("chapter_plans", sa.Column("chapter_title", sa.String(255), nullable=True))
    op.add_column("chapter_plans", sa.Column("pov", sa.String(128), nullable=True))
    op.add_column("chapter_plans", sa.Column("location", sa.String(255), nullable=True))
    op.add_column("chapter_plans", sa.Column("characters", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("chapter_plans", sa.Column("chapter_goal", sa.Text(), nullable=True))
    op.add_column("chapter_plans", sa.Column("emotional_arc", sa.Text(), nullable=True))
    op.add_column("chapter_plans", sa.Column("new_information", sa.Text(), nullable=True))
    op.add_column("chapter_plans", sa.Column("reveal", sa.Text(), nullable=True))
    op.add_column("chapter_plans", sa.Column("foreshadowing", sa.Text(), nullable=True))
    op.add_column("chapter_plans", sa.Column("setup", sa.Text(), nullable=True))
    op.add_column("chapter_plans", sa.Column("payoff", sa.Text(), nullable=True))
    op.add_column("chapter_plans", sa.Column("cliffhanger", sa.Text(), nullable=True))

    op.add_column("scene_plans", sa.Column("characters", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("scene_plans", sa.Column("turning_point", sa.Text(), nullable=True))
    op.add_column("scene_plans", sa.Column("dialogue_goal", sa.Text(), nullable=True))
    op.add_column("scene_plans", sa.Column("emotion", sa.Text(), nullable=True))
    op.add_column("scene_plans", sa.Column("information_revealed", sa.Text(), nullable=True))
    op.add_column("scene_plans", sa.Column("ending", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scene_plans", "ending")
    op.drop_column("scene_plans", "information_revealed")
    op.drop_column("scene_plans", "emotion")
    op.drop_column("scene_plans", "dialogue_goal")
    op.drop_column("scene_plans", "turning_point")
    op.drop_column("scene_plans", "characters")

    op.drop_column("chapter_plans", "cliffhanger")
    op.drop_column("chapter_plans", "payoff")
    op.drop_column("chapter_plans", "setup")
    op.drop_column("chapter_plans", "foreshadowing")
    op.drop_column("chapter_plans", "reveal")
    op.drop_column("chapter_plans", "new_information")
    op.drop_column("chapter_plans", "emotional_arc")
    op.drop_column("chapter_plans", "chapter_goal")
    op.drop_column("chapter_plans", "characters")
    op.drop_column("chapter_plans", "location")
    op.drop_column("chapter_plans", "pov")
    op.drop_column("chapter_plans", "chapter_title")
    op.drop_column("chapter_plans", "chapter_number")

    op.drop_column("characters", "status")
    op.drop_column("characters", "character_arc")
    op.drop_column("characters", "speech_style")
    op.drop_column("characters", "external_conflict")
    op.drop_column("characters", "internal_conflict")
    op.drop_column("characters", "weakness")
    op.drop_column("characters", "strength")
    op.drop_column("characters", "secret")
    op.drop_column("characters", "fear")
    op.drop_column("characters", "motivation")
    op.drop_column("characters", "goal")
    op.drop_column("characters", "background")

    op.drop_column("story_bibles", "heat_level")
    op.drop_column("story_bibles", "violence_level")
    op.drop_column("story_bibles", "romance_level")
    op.drop_column("story_bibles", "chapter_word_count")
    op.drop_column("story_bibles", "target_word_count")
    op.drop_column("story_bibles", "tense")
    op.drop_column("story_bibles", "pov")
    op.drop_column("story_bibles", "narrative_style")
