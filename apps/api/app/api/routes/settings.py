from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_engine, get_llm_provider
from app.api.routes.automation import _recover_queued_tasks
from app.api.schemas import LLMSettingsOut, LLMSettingsPatch
from app.db.models.llm import LLMConfig
from novel_engine.domain.errors import NotFoundError
from novel_engine.providers.base import LLMProvider
from novel_engine.providers.types import ChatMessage
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["settings"])


@router.post("/projects/{project_id}/settings/llm/test")
async def test_llm_settings(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> dict[str, str]:
    """Make a real provider request with request headers; do not persist anything."""
    await engine.get_project(project_id)
    result = await provider.generate(
        [ChatMessage(role="user", content="Reply with exactly: connection ok")],
        temperature=0,
    )
    return {"status": "ok", "provider": result.provider, "model": result.model}


@router.post("/settings/llm/test")
async def test_global_llm_settings(
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> dict[str, str]:
    """Test the global form headers without reading or writing project settings."""
    result = await provider.generate(
        [ChatMessage(role="user", content="Reply with exactly: connection ok")],
        temperature=0,
    )
    return {"status": "ok", "provider": result.provider, "model": result.model}


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


@router.patch("/settings/llm")
async def patch_global_llm_settings(
    body: dict,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str | bool | None]:
    """Persist the global model connection for background automation."""
    name = str(body.get("name") or "global-generation")
    row = await session.scalar(
        select(LLMConfig).where(LLMConfig.project_id.is_(None), LLMConfig.name == name)
    )
    if row is None:
        row = LLMConfig(
            project_id=None,
            name=name,
            provider=str(body.get("provider") or "deepseek"),
            model=str(body.get("model") or "deepseek-chat"),
            is_default=True,
        )
        session.add(row)
    row.provider = str(body.get("provider") or row.provider)
    row.model = str(body.get("model") or row.model)
    row.base_url = str(body.get("base_url") or "") or None
    row.api_key = str(body.get("api_key") or "") or row.api_key
    row.is_default = True
    await session.commit()
    await _recover_queued_tasks(retry_provider_failures=True)
    return {"status": "saved", "provider": row.provider, "model": row.model, "api_key_configured": bool(row.api_key)}


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
