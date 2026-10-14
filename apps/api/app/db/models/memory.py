from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.constants import EMBEDDING_DIMENSIONS
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from novel_engine.models.enums import EpistemicStatus, Importance, MemoryLayer, MemoryType

if TYPE_CHECKING:
    from app.db.models.chapter import Chapter
    from app.db.models.character import Character
    from app.db.models.project import NovelProject


class StoryMemory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Long-term story memory with optional pgvector embedding."""

    __tablename__ = "story_memories"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MemoryType.FACT.value,
        index=True,
    )
    layer: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=MemoryLayer.CHAPTER.value,
        index=True,
    )
    epistemic_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EpistemicStatus.TENTATIVE_FACT.value,
        index=True,
    )
    importance: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=Importance.MEDIUM.value,
        index=True,
    )
    source_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"),
        index=True,
    )
    chapter_number: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    known_by: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    unknown_to: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    embedding = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=True)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="memories")
    source_chapter: Mapped[Chapter | None] = relationship()
    character: Mapped[Character | None] = relationship()


class TimelineEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """In-world chronology plus causal order (sequence + optional cause)."""

    __tablename__ = "timeline_events"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "sequence",
            name="uq_timeline_events_project_sequence",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    in_world_time: Mapped[str | None] = mapped_column(String(128))
    in_world_offset_days: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    caused_by_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("timeline_events.id", ondelete="SET NULL"),
        index=True,
    )
    involved_character_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="timeline_events")
    chapter: Mapped[Chapter | None] = relationship()
    caused_by: Mapped[TimelineEvent | None] = relationship(
        remote_side="TimelineEvent.id",
        foreign_keys=[caused_by_event_id],
    )
