from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from novel_engine.models.enums import CharacterRole

if TYPE_CHECKING:
    from app.db.models.chapter import Chapter
    from app.db.models.plot import StoryArc
    from app.db.models.project import NovelProject


class Character(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Relatively stable character identity. Dynamic facts live on CharacterState."""

    __tablename__ = "characters"
    __table_args__ = (
        Index("ix_characters_project_id_name", "project_id", "name"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CharacterRole.SUPPORTING.value,
        index=True,
    )
    species: Mapped[str | None] = mapped_column(String(64))
    rank: Mapped[str | None] = mapped_column(String(64))
    gender: Mapped[str | None] = mapped_column(String(32))
    appearance: Mapped[str | None] = mapped_column(Text)
    personality: Mapped[str | None] = mapped_column(Text)
    backstory: Mapped[str | None] = mapped_column(Text)
    background: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    motivation: Mapped[str | None] = mapped_column(Text)
    fear: Mapped[str | None] = mapped_column(Text)
    secret: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[str | None] = mapped_column(Text)
    weakness: Mapped[str | None] = mapped_column(Text)
    internal_conflict: Mapped[str | None] = mapped_column(Text)
    external_conflict: Mapped[str | None] = mapped_column(Text)
    speech_style: Mapped[str | None] = mapped_column(Text)
    character_arc: Mapped[str | None] = mapped_column(Text)
    secrets: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tropes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="characters")
    states: Mapped[list[CharacterState]] = relationship(
        back_populates="character",
        cascade="all, delete-orphan",
    )
    outgoing_relationships: Mapped[list[Relationship]] = relationship(
        back_populates="source_character",
        foreign_keys="Relationship.source_character_id",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[list[Relationship]] = relationship(
        back_populates="target_character",
        foreign_keys="Relationship.target_character_id",
    )


class CharacterState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Snapshot of a character at a chapter or arc. Not a substitute for Character."""

    __tablename__ = "character_states"
    __table_args__ = (
        UniqueConstraint(
            "character_id",
            "chapter_id",
            name="uq_character_states_character_chapter",
        ),
        Index("ix_character_states_project_character", "project_id", "character_id"),
        Index("ix_character_states_chapter_id", "chapter_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
    )
    story_arc_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("story_arcs.id", ondelete="SET NULL"),
        index=True,
    )
    current_location: Mapped[str | None] = mapped_column(String(255))
    emotional_state: Mapped[str | None] = mapped_column(String(128))
    relationship_status: Mapped[str | None] = mapped_column(String(128))
    knowledge: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    secrets_known: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    powers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    health_status: Mapped[str | None] = mapped_column(String(128))
    is_current: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    character: Mapped[Character] = relationship(back_populates="states")
    chapter: Mapped[Chapter | None] = relationship()
    story_arc: Mapped[StoryArc | None] = relationship()


class Relationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Directed relationship between two characters (mate, rival, pack, etc.)."""

    __tablename__ = "relationships"
    __table_args__ = (
        Index(
            "ix_relationships_project_source_target",
            "project_id",
            "source_character_id",
            "target_character_id",
        ),
        Index("ix_relationships_type", "relationship_type"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    description: Mapped[str | None] = mapped_column(Text)
    started_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
    )
    ended_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="relationships")
    source_character: Mapped[Character] = relationship(
        back_populates="outgoing_relationships",
        foreign_keys=[source_character_id],
    )
    target_character: Mapped[Character] = relationship(
        back_populates="incoming_relationships",
        foreign_keys=[target_character_id],
    )
    started_chapter: Mapped[Chapter | None] = relationship(foreign_keys=[started_chapter_id])
    ended_chapter: Mapped[Chapter | None] = relationship(foreign_keys=[ended_chapter_id])
