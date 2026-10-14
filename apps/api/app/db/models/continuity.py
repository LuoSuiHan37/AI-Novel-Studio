from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from novel_engine.models.enums import (
    ContinuityIssueStatus,
    ContinuitySeverity,
    ForeshadowStatus,
    HookStatus,
    HookType,
    Importance,
)

if TYPE_CHECKING:
    from app.db.models.chapter import Chapter
    from app.db.models.character import Character
    from app.db.models.project import NovelProject


class Hook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hooks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hook_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=HookType.CLIFFHANGER.value,
        index=True,
    )
    setup_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    resolved_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=HookStatus.PLANNED.value,
        index=True,
    )
    importance: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=Importance.HIGH.value,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="hooks")
    setup_chapter: Mapped[Chapter | None] = relationship(foreign_keys=[setup_chapter_id])
    resolved_chapter: Mapped[Chapter | None] = relationship(foreign_keys=[resolved_chapter_id])


class Foreshadowing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "foreshadowings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    setup_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    expected_payoff_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    actual_payoff_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ForeshadowStatus.PLANNED.value,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    clue_text: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="foreshadowings")
    setup_chapter: Mapped[Chapter | None] = relationship(foreign_keys=[setup_chapter_id])
    expected_payoff_chapter: Mapped[Chapter | None] = relationship(
        foreign_keys=[expected_payoff_chapter_id]
    )
    actual_payoff_chapter: Mapped[Chapter | None] = relationship(
        foreign_keys=[actual_payoff_chapter_id]
    )


class ContinuityIssue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "continuity_issues"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    related_character_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"),
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ContinuitySeverity.MEDIUM.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ContinuityIssueStatus.OPEN.value,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="continuity_issues")
    chapter: Mapped[Chapter | None] = relationship()
    related_character: Mapped[Character | None] = relationship()
