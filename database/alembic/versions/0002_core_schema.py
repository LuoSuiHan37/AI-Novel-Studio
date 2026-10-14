"""Core novel schema.

Revision ID: 0002_core_schema
Revises: 0001_enable_pgvector
Create Date: 2026-10-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002_core_schema"
down_revision: Union[str, Sequence[str], None] = "0001_enable_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = sa.Uuid(as_uuid=True)
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "novel_projects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("genre", sa.String(128), nullable=False, server_default="werewolf_romance"),
        sa.Column("tropes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("target_platform", sa.String(64)),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("logline", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="planning"),
        sa.Column("current_stage", sa.String(32), nullable=False, server_default="idea"),
        sa.Column("word_count_target", sa.Integer()),
        sa.Column("chapter_count_target", sa.Integer()),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_novel_projects_status", "novel_projects", ["status"])
    op.create_index("ix_novel_projects_current_stage", "novel_projects", ["current_stage"])
    op.create_index("ix_novel_projects_title", "novel_projects", ["title"])

    op.create_table(
        "story_bibles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("premise", sa.Text()),
        sa.Column("theme", sa.Text()),
        sa.Column("tone", sa.String(255)),
        sa.Column("tropes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("logline", sa.Text()),
        sa.Column("synopsis", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_story_bibles_project_id"),
    )
    op.create_index("ix_story_bibles_project_id", "story_bibles", ["project_id"])

    op.create_table(
        "world_bibles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("geography", sa.Text()),
        sa.Column("factions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_world_bibles_project_id"),
    )
    op.create_index("ix_world_bibles_project_id", "world_bibles", ["project_id"])

    op.create_table(
        "world_rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("world_bible_id", UUID, sa.ForeignKey("world_bibles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_hard_constraint", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_world_rules_world_bible_id", "world_rules", ["world_bible_id"])

    op.create_table(
        "llm_configs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="openai_compatible"),
        sa.Column("base_url", sa.String(512)),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("api_key_env_name", sa.String(128)),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("extra_params", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_configs_project_id", "llm_configs", ["project_id"])
    op.create_index(
        "uq_llm_configs_global_name",
        "llm_configs",
        ["name"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_index(
        "uq_llm_configs_project_name",
        "llm_configs",
        ["project_id", "name"],
        unique=True,
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )

    op.create_table(
        "master_plots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("structure", sa.String(64), nullable=False, server_default="three_act"),
        sa.Column("summary", sa.Text()),
        sa.Column("beats", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_master_plots_project_id", "master_plots", ["project_id"])

    op.create_table(
        "story_arcs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("master_plot_id", UUID, sa.ForeignKey("master_plots.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("arc_type", sa.String(64), nullable=False, server_default="main"),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("start_chapter_number", sa.Integer()),
        sa.Column("end_chapter_number", sa.Integer()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "sequence", name="uq_story_arcs_project_sequence"),
    )
    op.create_index("ix_story_arcs_project_id", "story_arcs", ["project_id"])
    op.create_index("ix_story_arcs_master_plot_id", "story_arcs", ["master_plot_id"])

    op.create_table(
        "characters",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("aliases", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("role", sa.String(32), nullable=False, server_default="supporting"),
        sa.Column("species", sa.String(64)),
        sa.Column("rank", sa.String(64)),
        sa.Column("gender", sa.String(32)),
        sa.Column("appearance", sa.Text()),
        sa.Column("personality", sa.Text()),
        sa.Column("backstory", sa.Text()),
        sa.Column("goals", sa.Text()),
        sa.Column("secrets", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tropes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_characters_project_id", "characters", ["project_id"])
    op.create_index("ix_characters_role", "characters", ["role"])
    op.create_index("ix_characters_project_id_name", "characters", ["project_id", "name"])

    op.create_table(
        "chapters",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_arc_id", UUID, sa.ForeignKey("story_arcs.id", ondelete="SET NULL")),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("current_revision_id", UUID),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "chapter_number", name="uq_chapters_project_number"),
        sa.CheckConstraint(
            "status IN ('draft', 'reviewed', 'approved', 'published')",
            name="ck_chapters_status",
        ),
    )
    op.create_index("ix_chapters_project_id", "chapters", ["project_id"])
    op.create_index("ix_chapters_story_arc_id", "chapters", ["story_arc_id"])
    op.create_index("ix_chapters_status", "chapters", ["status"])

    op.create_table(
        "chapter_plans",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("goal", sa.Text()),
        sa.Column("conflict", sa.Text()),
        sa.Column("emotional_beat", sa.Text()),
        sa.Column("hook_plan", sa.Text()),
        sa.Column("outline", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("chapter_id", "version", name="uq_chapter_plans_chapter_version"),
    )
    op.create_index("ix_chapter_plans_project_id", "chapter_plans", ["project_id"])
    op.create_index("ix_chapter_plans_chapter_id", "chapter_plans", ["chapter_id"])

    op.create_table(
        "scene_plans",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("chapter_plan_id", UUID, sa.ForeignKey("chapter_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("pov_character_id", UUID, sa.ForeignKey("characters.id", ondelete="SET NULL")),
        sa.Column("location", sa.String(255)),
        sa.Column("goal", sa.Text()),
        sa.Column("conflict", sa.Text()),
        sa.Column("outcome", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("chapter_plan_id", "scene_number", name="uq_scene_plans_plan_number"),
    )
    op.create_index("ix_scene_plans_chapter_plan_id", "scene_plans", ["chapter_plan_id"])
    op.create_index("ix_scene_plans_pov_character_id", "scene_plans", ["pov_character_id"])

    op.create_table(
        "chapter_revisions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("change_summary", sa.Text()),
        sa.Column("restored_from_revision_id", UUID, sa.ForeignKey("chapter_revisions.id", ondelete="SET NULL")),
        sa.Column("created_by", sa.String(32), nullable=False, server_default="human"),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("chapter_id", "revision_number", name="uq_chapter_revisions_chapter_number"),
    )
    op.create_index("ix_chapter_revisions_chapter_id", "chapter_revisions", ["chapter_id"])
    op.create_index("ix_chapter_revisions_restored_from_revision_id", "chapter_revisions", ["restored_from_revision_id"])

    op.create_foreign_key(
        "fk_chapters_current_revision_id",
        "chapters",
        "chapter_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "chapter_summaries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_events", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chapter_summaries_chapter_id", "chapter_summaries", ["chapter_id"])

    op.create_table(
        "character_states",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", UUID, sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("story_arc_id", UUID, sa.ForeignKey("story_arcs.id", ondelete="SET NULL")),
        sa.Column("current_location", sa.String(255)),
        sa.Column("emotional_state", sa.String(128)),
        sa.Column("relationship_status", sa.String(128)),
        sa.Column("knowledge", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("secrets_known", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("powers", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("health_status", sa.String(128)),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("character_id", "chapter_id", name="uq_character_states_character_chapter"),
    )
    op.create_index("ix_character_states_project_id", "character_states", ["project_id"])
    op.create_index("ix_character_states_character_id", "character_states", ["character_id"])
    op.create_index("ix_character_states_chapter_id", "character_states", ["chapter_id"])
    op.create_index("ix_character_states_story_arc_id", "character_states", ["story_arc_id"])
    op.create_index("ix_character_states_is_current", "character_states", ["is_current"])
    op.create_index(
        "ix_character_states_project_character",
        "character_states",
        ["project_id", "character_id"],
    )

    op.create_table(
        "relationships",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_character_id", UUID, sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_character_id", UUID, sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="active"),
        sa.Column("description", sa.Text()),
        sa.Column("started_chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("ended_chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_relationships_project_id", "relationships", ["project_id"])
    op.create_index("ix_relationships_source_character_id", "relationships", ["source_character_id"])
    op.create_index("ix_relationships_target_character_id", "relationships", ["target_character_id"])
    op.create_index("ix_relationships_type", "relationships", ["relationship_type"])
    op.create_index(
        "ix_relationships_project_source_target",
        "relationships",
        ["project_id", "source_character_id", "target_character_id"],
    )

    op.create_table(
        "story_memories",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", sa.String(32), nullable=False, server_default="fact"),
        sa.Column("importance", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("source_chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("character_id", UUID, sa.ForeignKey("characters.id", ondelete="SET NULL")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536)),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_story_memories_project_id", "story_memories", ["project_id"])
    op.create_index("ix_story_memories_memory_type", "story_memories", ["memory_type"])
    op.create_index("ix_story_memories_importance", "story_memories", ["importance"])
    op.create_index("ix_story_memories_source_chapter_id", "story_memories", ["source_chapter_id"])
    op.create_index("ix_story_memories_character_id", "story_memories", ["character_id"])
    op.execute(
        "CREATE INDEX ix_story_memories_embedding ON story_memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "timeline_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("in_world_time", sa.String(128)),
        sa.Column("in_world_offset_days", sa.Integer()),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("caused_by_event_id", UUID, sa.ForeignKey("timeline_events.id", ondelete="SET NULL")),
        sa.Column("involved_character_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "sequence", name="uq_timeline_events_project_sequence"),
    )
    op.create_index("ix_timeline_events_project_id", "timeline_events", ["project_id"])
    op.create_index("ix_timeline_events_chapter_id", "timeline_events", ["chapter_id"])
    op.create_index("ix_timeline_events_caused_by_event_id", "timeline_events", ["caused_by_event_id"])

    op.create_table(
        "hooks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hook_type", sa.String(32), nullable=False, server_default="cliffhanger"),
        sa.Column("setup_chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("resolved_chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False, server_default="planned"),
        sa.Column("importance", sa.String(16), nullable=False, server_default="high"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_hooks_project_id", "hooks", ["project_id"])
    op.create_index("ix_hooks_hook_type", "hooks", ["hook_type"])
    op.create_index("ix_hooks_setup_chapter_id", "hooks", ["setup_chapter_id"])
    op.create_index("ix_hooks_resolved_chapter_id", "hooks", ["resolved_chapter_id"])
    op.create_index("ix_hooks_status", "hooks", ["status"])

    op.create_table(
        "foreshadowings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("setup_chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("expected_payoff_chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("actual_payoff_chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False, server_default="planned"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("clue_text", sa.Text()),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_foreshadowings_project_id", "foreshadowings", ["project_id"])
    op.create_index("ix_foreshadowings_setup_chapter_id", "foreshadowings", ["setup_chapter_id"])
    op.create_index("ix_foreshadowings_expected_payoff_chapter_id", "foreshadowings", ["expected_payoff_chapter_id"])
    op.create_index("ix_foreshadowings_actual_payoff_chapter_id", "foreshadowings", ["actual_payoff_chapter_id"])
    op.create_index("ix_foreshadowings_status", "foreshadowings", ["status"])

    op.create_table(
        "continuity_issues",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="SET NULL")),
        sa.Column("related_character_id", UUID, sa.ForeignKey("characters.id", ondelete="SET NULL")),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_continuity_issues_project_id", "continuity_issues", ["project_id"])
    op.create_index("ix_continuity_issues_chapter_id", "continuity_issues", ["chapter_id"])
    op.create_index("ix_continuity_issues_related_character_id", "continuity_issues", ["related_character_id"])
    op.create_index("ix_continuity_issues_severity", "continuity_issues", ["severity"])
    op.create_index("ix_continuity_issues_status", "continuity_issues", ["status"])


def downgrade() -> None:
    op.drop_table("continuity_issues")
    op.drop_table("foreshadowings")
    op.drop_table("hooks")
    op.drop_table("timeline_events")
    op.execute("DROP INDEX IF EXISTS ix_story_memories_embedding")
    op.drop_table("story_memories")
    op.drop_table("relationships")
    op.drop_table("character_states")
    op.drop_table("chapter_summaries")
    op.drop_constraint("fk_chapters_current_revision_id", "chapters", type_="foreignkey")
    op.drop_table("chapter_revisions")
    op.drop_table("scene_plans")
    op.drop_table("chapter_plans")
    op.drop_table("chapters")
    op.drop_table("characters")
    op.drop_table("story_arcs")
    op.drop_table("master_plots")
    op.drop_table("llm_configs")
    op.drop_table("world_rules")
    op.drop_table("world_bibles")
    op.drop_table("story_bibles")
    op.drop_table("novel_projects")
