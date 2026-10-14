from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from novel_engine.models.enums import PipelineStage, ProjectStatus

if TYPE_CHECKING:
    from app.db.models.bible import StoryBible, WorldBible
    from app.db.models.chapter import Chapter
    from app.db.models.character import Character, Relationship
    from app.db.models.continuity import ContinuityIssue, Foreshadowing, Hook
    from app.db.models.llm import LLMConfig
    from app.db.models.memory import StoryMemory, TimelineEvent
    from app.db.models.plot import MasterPlot, StoryArc


class NovelProject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Root writing project. All story entities hang off this row."""

    __tablename__ = "novel_projects"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(128), nullable=False, default="werewolf_romance")
    tropes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    target_platform: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    logline: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProjectStatus.PLANNING.value,
        index=True,
    )
    current_stage: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PipelineStage.IDEA.value,
        index=True,
    )
    word_count_target: Mapped[int | None] = mapped_column(Integer)
    chapter_count_target: Mapped[int | None] = mapped_column(Integer)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    story_bible: Mapped[StoryBible | None] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )
    world_bible: Mapped[WorldBible | None] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )
    characters: Mapped[list[Character]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    relationships: Mapped[list[Relationship]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    master_plots: Mapped[list[MasterPlot]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    story_arcs: Mapped[list[StoryArc]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    memories: Mapped[list[StoryMemory]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    timeline_events: Mapped[list[TimelineEvent]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    hooks: Mapped[list[Hook]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    foreshadowings: Mapped[list[Foreshadowing]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    continuity_issues: Mapped[list[ContinuityIssue]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    llm_configs: Mapped[list[LLMConfig]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<NovelProject id={self.id} title={self.title!r}>"
