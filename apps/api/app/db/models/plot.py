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
    from app.db.models.chapter import Chapter
    from app.db.models.project import NovelProject


class MasterPlot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Book-level plot (beats, structure). Multiple rows allow alternate outlines."""

    __tablename__ = "master_plots"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    structure: Mapped[str] = mapped_column(String(64), nullable=False, default="three_act")
    summary: Mapped[str | None] = mapped_column(Text)
    beats: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ApprovalStatus.DRAFT.value,
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="master_plots")
    story_arcs: Mapped[list[StoryArc]] = relationship(back_populates="master_plot")


class StoryArc(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "story_arcs"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_story_arcs_project_sequence"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    master_plot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("master_plots.id", ondelete="SET NULL"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    arc_type: Mapped[str] = mapped_column(String(64), nullable=False, default="main")
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    start_chapter_number: Mapped[int | None] = mapped_column(Integer)
    end_chapter_number: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ApprovalStatus.DRAFT.value,
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject] = relationship(back_populates="story_arcs")
    master_plot: Mapped[MasterPlot | None] = relationship(back_populates="story_arcs")
    chapters: Mapped[list[Chapter]] = relationship(back_populates="story_arc")
