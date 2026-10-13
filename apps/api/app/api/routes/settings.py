from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_engine
from app.api.schemas import LLMSettingsOut, LLMSettingsPatch
from app.db.models.llm import LLMConfig
from novel_engine.domain.errors import NotFoundError
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["settings"])


@router.get("/projects/{project_id}/settings/llm")
async def get_llm_settings(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> LLMSettingsOut:
    await engine.get_project(project_id)
    session = _session(engine)
    row = await session.scalar(
        select(LLMConfig)
        .where(LLMConfig.project_id == project_id)
        .order_by(LLMConfig.is_default.desc())
    )
    if row is None:
        raise NotFoundError("llm settings not found")
    return _out(row)


@router.patch("/projects/{project_id}/settings/llm")
async def patch_llm_settings(
    project_id: UUID,
    body: LLMSettingsPatch,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> LLMSettingsOut:
    await engine.get_project(project_id)
    session = _session(engine)
    row = await session.scalar(
        select(LLMConfig).where(LLMConfig.project_id == project_id, LLMConfig.name == body.name)
    )
    if row is None:
        row = LLMConfig(project_id=project_id, name=body.name, provider=body.provider, model=body.model)
        session.add(row)
    row.provider = body.provider
    row.model = body.model
    row.base_url = body.base_url
    row.temperature = body.temperature
    row.max_tokens = body.max_tokens
    row.is_default = body.is_default
    row.api_key_env_name = body.api_key_env_name
    await session.commit()
    await session.refresh(row)
    return _out(row)


def _session(engine: NovelEngine) -> AsyncSession:
    session = getattr(engine.uow, "session", None)
    if not isinstance(session, AsyncSession):
        raise NotFoundError("llm settings require sql persistence")
    return session


def _out(row: LLMConfig) -> LLMSettingsOut:
    return LLMSettingsOut(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        provider=row.provider,
        model=row.model,
        base_url=row.base_url,
        temperature=row.temperature,
        max_tokens=row.max_tokens,
        is_default=row.is_default,
        api_key_env_name=row.api_key_env_name,
    )
