from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import Depends, Header, Request
from pydantic import BaseModel, SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.core.config import Settings, get_settings
from app.db.models.llm import LLMConfig
from app.db.session import get_db
from app.llm.factory import (
    create_provider,
    provider_config_from_settings,
    reviewer_provider_config_from_settings,
)
from novel_engine.models.enums import LLMProvider as LLMProviderName
from novel_engine.domain.errors import InvalidStateError
from novel_engine.providers.base import LLMProvider
from novel_engine.services.engine import NovelEngine
from novel_engine.workflows.agent_workflow import AgentWorkflow

logger = logging.getLogger("ai-novel-studio.api")


class Actor(BaseModel):
    id: str
    is_authenticated: bool


def _request_project_id(request: Request, header_value: str | None) -> uuid.UUID | None:
    """Use the route project as the authority for project-scoped provider config."""
    route_value = request.path_params.get("project_id")
    route_id = None
    if route_value is not None:
        try:
            route_id = uuid.UUID(str(route_value))
        except ValueError as exc:
            raise InvalidStateError("invalid project id in request path") from exc
    if header_value:
        try:
            header_id = uuid.UUID(header_value)
        except ValueError as exc:
            raise InvalidStateError("invalid X-Project-ID header") from exc
        if route_id is not None and header_id != route_id:
            raise InvalidStateError("X-Project-ID does not match the project in the request path")
        return header_id
    return route_id


async def get_engine(session: Annotated[AsyncSession, Depends(get_db)]) -> NovelEngine:
    return NovelEngine(SqlAlchemyUnitOfWork(session))


async def get_actor(
    x_actor: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Actor:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    actor_id = x_actor or ("authenticated" if token else "anonymous")
    return Actor(id=actor_id, is_authenticated=bool(token) or bool(x_actor))


async def get_llm_provider(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db)],
    x_project_id: Annotated[str | None, Header()] = None,
    x_llm_api_key: Annotated[str | None, Header()] = None,
    x_llm_base_url: Annotated[str | None, Header()] = None,
    x_llm_model: Annotated[str | None, Header()] = None,
    x_llm_provider: Annotated[str | None, Header()] = None,
) -> LLMProvider:
    row = None
    project_id = _request_project_id(request, x_project_id)
    if project_id is not None:
        row = await session.scalar(
            select(LLMConfig)
            .where(LLMConfig.project_id == project_id)
            .order_by(LLMConfig.is_default.desc())
        )
    config = provider_config_from_settings(settings, row=row)
    updates: dict = {}
    if x_llm_provider:
        provider = x_llm_provider.strip().lower()
        # Compatibility with clients from before the provider selector used
        # concrete providers. DeepSeek is the app's default OpenAI-compatible
        # provider, so an old generic value without a custom endpoint can be
        # safely migrated here as well.
        if provider == LLMProviderName.OPENAI_COMPATIBLE.value and not x_llm_base_url:
            provider = LLMProviderName.DEEPSEEK.value
        updates["provider"] = LLMProviderName(provider)
    if x_llm_model:
        updates["model"] = x_llm_model
    if x_llm_base_url:
        updates["base_url"] = x_llm_base_url
    if x_llm_api_key:
        updates["api_key"] = SecretStr(x_llm_api_key)
    if updates:
        config = config.model_copy(update=updates)
    return create_provider(config)


async def get_optional_llm_provider(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db)],
    x_project_id: Annotated[str | None, Header()] = None,
    x_llm_api_key: Annotated[str | None, Header()] = None,
    x_llm_base_url: Annotated[str | None, Header()] = None,
    x_llm_model: Annotated[str | None, Header()] = None,
    x_llm_provider: Annotated[str | None, Header()] = None,
) -> LLMProvider | None:
    """Build a provider when configured, but allow non-LLM research stages to run."""
    row = None
    project_id = _request_project_id(request, x_project_id)
    if project_id is not None:
        row = await session.scalar(
            select(LLMConfig)
            .where(LLMConfig.project_id == project_id)
            .order_by(LLMConfig.is_default.desc())
        )
    config = provider_config_from_settings(settings, row=row)
    if x_llm_api_key:
        config = config.model_copy(update={"api_key": SecretStr(x_llm_api_key)})
    if not config.revealed_api_key():
        return None
    updates: dict = {}
    if x_llm_provider:
        updates["provider"] = LLMProviderName(x_llm_provider.strip().lower())
    if x_llm_model:
        updates["model"] = x_llm_model
    if x_llm_base_url:
        updates["base_url"] = x_llm_base_url
    if updates:
        config = config.model_copy(update=updates)
    return create_provider(config)


async def get_workflow(provider: Annotated[LLMProvider, Depends(get_llm_provider)]) -> AgentWorkflow:
    return AgentWorkflow(provider)


async def get_review_workflow(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db)],
    x_project_id: Annotated[str | None, Header()] = None,
    x_review_api_key: Annotated[str | None, Header()] = None,
    x_review_base_url: Annotated[str | None, Header()] = None,
    x_review_model: Annotated[str | None, Header()] = None,
    x_review_provider: Annotated[str | None, Header()] = None,
    x_llm_provider: Annotated[str | None, Header()] = None,
    x_llm_model: Annotated[str | None, Header()] = None,
    x_llm_base_url: Annotated[str | None, Header()] = None,
) -> AgentWorkflow | None:
    config = reviewer_provider_config_from_settings(settings)
    if x_review_provider:
        provider = LLMProviderName(x_review_provider.strip().lower())
        base = provider_config_from_settings(settings)
        selected_review_model = x_review_model or (config.model if config is not None else base.model)
        config = base.model_copy(
            update={
                "provider": provider,
                "model": selected_review_model,
                "base_url": x_review_base_url or base.base_url,
                "api_key": SecretStr(x_review_api_key) if x_review_api_key else base.api_key,
                "temperature": 0.2,
            }
        )
    if config is None:
        return None
    generation_row = None
    project_id = _request_project_id(request, x_project_id)
    if project_id is not None:
        generation_row = await session.scalar(
            select(LLMConfig)
            .where(LLMConfig.project_id == project_id)
            .order_by(LLMConfig.is_default.desc())
        )
    generation_config = provider_config_from_settings(settings, row=generation_row)
    generation_updates: dict = {}
    if x_llm_provider:
        generation_updates["provider"] = LLMProviderName(x_llm_provider.strip().lower())
    if x_llm_model:
        generation_updates["model"] = x_llm_model
    if x_llm_base_url:
        generation_updates["base_url"] = x_llm_base_url
    if generation_updates:
        generation_config = generation_config.model_copy(update=generation_updates)

    def runtime_identity(provider_config):
        return (
            provider_config.provider.value,
            provider_config.model.strip().casefold(),
            (provider_config.base_url or "").rstrip("/").casefold(),
        )

    if runtime_identity(generation_config) == runtime_identity(config):
        raise InvalidStateError("生成模型和审查模型不能相同，必须配置独立审查模型")
    return AgentWorkflow(create_provider(config), role="independent-reviewer")


def confirmed_by(explicit: str | None, actor: Actor) -> str:
    return (explicit or actor.id or "anonymous").strip()
