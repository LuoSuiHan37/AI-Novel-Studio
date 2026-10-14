from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from novel_engine.models.enums import ApprovalStatus, ChapterStatus

if TYPE_CHECKING:
    from app.db.models.character import Character
    from app.db.models.plot import StoryArc
    from app.db.models.project import NovelProject


class Chapter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("project_id", "chapter_number", name="uq_chapters_project_number"),
        CheckConstraint(
            "status IN ('draft', 'reviewed', 'approved', 'published')",
            name="ck_chapters_status",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    story_arc_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("story_arcs.id", ondelete="SET NULL"),
        index=True,
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ChapterStatus.DRAFT.value,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "chapter_revisions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_chapters_current_revision_id",
        ),
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="chapters")
    story_arc: Mapped[StoryArc | None] = relationship(back_populates="chapters")
    current_revision: Mapped[ChapterRevision | None] = relationship(
        foreign_keys=[current_revision_id],
        post_update=True,
    )
    plans: Mapped[list[ChapterPlan]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list[ChapterRevision]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        foreign_keys="ChapterRevision.chapter_id",
    )
    summaries: Mapped[list[ChapterSummary]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
    )


class ChapterPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapter_plans"
    __table_args__ = (
        UniqueConstraint("chapter_id", "version", name="uq_chapter_plans_chapter_version"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chapter_number: Mapped[int | None] = mapped_column(Integer)
    chapter_title: Mapped[str | None] = mapped_column(String(255))
    pov: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(255))
    characters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    chapter_goal: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    conflict: Mapped[str | None] = mapped_column(Text)
    emotional_beat: Mapped[str | None] = mapped_column(Text)
    emotional_arc: Mapped[str | None] = mapped_column(Text)
    new_information: Mapped[str | None] = mapped_column(Text)
    reveal: Mapped[str | None] = mapped_column(Text)
    foreshadowing: Mapped[str | None] = mapped_column(Text)
    setup: Mapped[str | None] = mapped_column(Text)
    payoff: Mapped[str | None] = mapped_column(Text)
    cliffhanger: Mapped[str | None] = mapped_column(Text)
    hook_plan: Mapped[str | None] = mapped_column(Text)
    outline: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ApprovalStatus.DRAFT.value,
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    chapter: Mapped[Chapter] = relationship(back_populates="plans")
    scenes: Mapped[list[ScenePlan]] = relationship(
        back_populates="chapter_plan",
        cascade="all, delete-orphan",
        order_by="ScenePlan.scene_number",
    )


class ScenePlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scene_plans"
    __table_args__ = (
        UniqueConstraint(
            "chapter_plan_id",
            "scene_number",
            name="uq_scene_plans_plan_number",
        ),
    )

    chapter_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapter_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pov_character_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"),
        index=True,
    )
    location: Mapped[str | None] = mapped_column(String(255))
    characters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    goal: Mapped[str | None] = mapped_column(Text)
    conflict: Mapped[str | None] = mapped_column(Text)
    turning_point: Mapped[str | None] = mapped_column(Text)
    dialogue_goal: Mapped[str | None] = mapped_column(Text)
    emotion: Mapped[str | None] = mapped_column(Text)
    information_revealed: Mapped[str | None] = mapped_column(Text)
    ending: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    chapter_plan: Mapped[ChapterPlan] = relationship(back_populates="scenes")
    pov_character: Mapped[Character | None] = relationship()


class ChapterRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable snapshot of chapter text. Restore by copying into a new revision."""

    __tablename__ = "chapter_revisions"
    __table_args__ = (
        UniqueConstraint(
            "chapter_id",
            "revision_number",
            name="uq_chapter_revisions_chapter_number",
        ),
    )

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_summary: Mapped[str | None] = mapped_column(Text)
    restored_from_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapter_revisions.id", ondelete="SET NULL"),
        index=True,
    )
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="human")
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    chapter: Mapped[Chapter] = relationship(
        back_populates="revisions",
        foreign_keys=[chapter_id],
    )
    restored_from: Mapped[ChapterRevision | None] = relationship(
        remote_side="ChapterRevision.id",
        foreign_keys=[restored_from_revision_id],
    )


class ChapterSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapter_summaries"
    __table_args__ = (UniqueConstraint("chapter_id", name="uq_chapter_summaries_chapter_id"),)

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_events: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    new_facts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    character_changes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    new_secrets: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    resolved_secrets: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    unresolved_hooks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    location: Mapped[str | None] = mapped_column(String(255))
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    chapter: Mapped[Chapter] = relationship(back_populates="summaries")


async def restore_chapter_revision(
    session: AsyncSession,
    chapter: Chapter,
    revision: ChapterRevision,
) -> ChapterRevision:
    """Create a new revision whose content matches a historical one, then point the chapter at it."""

    if revision.chapter_id != chapter.id:
        raise ValueError("revision does not belong to the given chapter")

    max_number = await session.scalar(
        select(func.max(ChapterRevision.revision_number)).where(
            ChapterRevision.chapter_id == chapter.id
        )
    )
    next_number = (max_number or 0) + 1
    restored = ChapterRevision(
        chapter_id=chapter.id,
        revision_number=next_number,
        content=revision.content,
        word_count=revision.word_count,
        change_summary=f"Restored from revision {revision.revision_number}",
        restored_from_revision_id=revision.id,
        created_by="human",
    )
    session.add(restored)
    await session.flush()
    chapter.content = restored.content
    chapter.word_count = restored.word_count
    chapter.current_revision_id = restored.id
    chapter.status = ChapterStatus.DRAFT.value
    chapter.extra_metadata = {
        key: value for key, value in (chapter.extra_metadata or {}).items() if key != "audit"
    }
    return restored
