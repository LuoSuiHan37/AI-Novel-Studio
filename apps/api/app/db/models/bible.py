from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from novel_engine.models.enums import ApprovalStatus

if TYPE_CHECKING:
    from app.db.models.project import NovelProject


class StoryBible(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable story-level canon: premise, theme, tone. One per project."""

    __tablename__ = "story_bibles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_story_bibles_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    premise: Mapped[str | None] = mapped_column(Text)
    theme: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(String(255))
    tropes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    logline: Mapped[str | None] = mapped_column(Text)
    synopsis: Mapped[str | None] = mapped_column(Text)
    narrative_style: Mapped[str | None] = mapped_column(Text)
    pov: Mapped[str | None] = mapped_column(String(32))
    tense: Mapped[str | None] = mapped_column(String(16))
    target_word_count: Mapped[int | None] = mapped_column(Integer)
    chapter_word_count: Mapped[int | None] = mapped_column(Integer)
    romance_level: Mapped[str | None] = mapped_column(String(16))
    violence_level: Mapped[str | None] = mapped_column(String(16))
    heat_level: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ApprovalStatus.DRAFT.value,
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="story_bible")


class WorldBible(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Setting bible. One per project in v1."""

    __tablename__ = "world_bibles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_world_bibles_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    geography: Mapped[str | None] = mapped_column(Text)
    factions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ApprovalStatus.DRAFT.value,
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="world_bible")
    rules: Mapped[list[WorldRule]] = relationship(
        back_populates="world_bible",
        cascade="all, delete-orphan",
    )


class WorldRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hard or soft world constraint (pack law, mate bond, magic cost)."""

    __tablename__ = "world_rules"

    world_bible_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("world_bibles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_hard_constraint: Mapped[bool] = mapped_column(nullable=False, default=True)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    world_bible: Mapped[WorldBible] = relationship(back_populates="rules")
