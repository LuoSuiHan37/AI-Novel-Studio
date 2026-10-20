from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AutomationTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Durable audit record for an automatic writing operation."""

    __tablename__ = "automation_tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    progress_message: Mapped[str | None] = mapped_column(Text)
    stage_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    chapter_number: Mapped[int | None] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PublishTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-platform publication state; each platform can fail independently."""

    __tablename__ = "publish_tasks"
    __table_args__ = (UniqueConstraint("chapter_id", "platform", name="uq_publish_tasks_chapter_platform"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    local_chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_book_id: Mapped[str | None] = mapped_column(String(255))
    platform_chapter_number: Mapped[int | None] = mapped_column(Integer)
    platform_chapter_title: Mapped[str | None] = mapped_column(String(255))
    content_fingerprint: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="waiting_upload")
    progress_message: Mapped[str | None] = mapped_column(Text)
    stage_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    external_chapter_id: Mapped[str | None] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Project-level schedule. The worker can safely claim due rows later."""

    __tablename__ = "automation_schedules"
    __table_args__ = (UniqueConstraint("project_id", name="uq_automation_schedules_project"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    platforms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class AutomationNotification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persistent notification for failures requiring human action."""

    __tablename__ = "automation_notifications"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("automation_tasks.id", ondelete="SET NULL"), index=True
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="error")
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    read_at: Mapped[datetime | None]


class AutomationDailyQuota(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persistent per-project, per-platform daily publication counter."""

    __tablename__ = "automation_daily_quotas"
    __table_args__ = (UniqueConstraint("project_id", "platform", "quota_date", name="uq_automation_daily_quota"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    quota_date: Mapped[date] = mapped_column(nullable=False, index=True)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    published_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
