from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from novel_engine.models.enums import LLMProvider

if TYPE_CHECKING:
    from app.db.models.project import NovelProject


class LLMConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provider settings. API keys stay in environment variables, not in this table."""

    __tablename__ = "llm_configs"
    __table_args__ = (
        Index(
            "uq_llm_configs_global_name",
            "name",
            unique=True,
            postgresql_where=text("project_id IS NULL"),
        ),
        Index(
            "uq_llm_configs_project_name",
            "project_id",
            "name",
            unique=True,
            postgresql_where=text("project_id IS NOT NULL"),
        ),
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LLMProvider.OPENAI_COMPATIBLE.value,
    )
    base_url: Mapped[str | None] = mapped_column(String(512))
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_env_name: Mapped[str | None] = mapped_column(String(128))
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[NovelProject | None] = relationship(back_populates="llm_configs")
