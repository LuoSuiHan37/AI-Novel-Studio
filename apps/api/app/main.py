import logging
import hmac
import uuid
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.api.errors import (
    domain_error_handler,
    database_error_handler,
    http_exception_handler,
    provider_error_handler,
    validation_error_handler,
)
from app.api.routes import (
    arcs_router,
    automation_router,
    chapters_router,
    characters_router,
    health_router,
    memory_router,
    plot_router,
    research_router,
    projects_router,
    settings_router,
    story_router,
    world_router,
)
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import engine_lifespan
from app.api.routes.automation import _recover_queued_tasks, start_automation_scheduler
from novel_engine.domain.errors import DomainError
from novel_engine.providers.errors import ProviderError

logger = logging.getLogger("ai-novel-studio.api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.app_env.lower() in {"production", "prod"} and not settings.api_auth_token:
        raise RuntimeError("API_AUTH_TOKEN must be configured in production")
    setup_logging(settings.log_level)
    async with engine_lifespan(settings):
        # Recover persisted work before serving requests.  This makes a task
        # created before an API restart resume deterministically instead of
        # depending on a background tick that may be delayed or hidden.
        await _recover_queued_tasks()
        scheduler = start_automation_scheduler()
        try:
            yield
        finally:
            scheduler.cancel()
            await asyncio.gather(scheduler, return_exceptions=True)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="REST API for ai-novel-studio. Agents generate, automated audits gate persistence, and system actions are traceable.",
        lifespan=lifespan,
    )
    cors_kwargs: dict = {
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    # Dev: any localhost port (3000/3001/3020...). Prod: explicit allow-list only.
    if settings.app_env.lower() in {"development", "dev", "local"}:
        cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1)(:\d+)?"
    else:
        cors_kwargs["allow_origins"] = settings.cors_origin_list
    application.add_middleware(CORSMiddleware, **cors_kwargs)

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        protected = (
            settings.app_env.lower() in {"production", "prod"}
            and request.method != "OPTIONS"
            and request.url.path not in {"/health", "/health/db", "/docs", "/openapi.json", "/redoc"}
        )
        if protected:
            authorization = request.headers.get("Authorization", "")
            supplied = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
            if not supplied or not hmac.compare_digest(supplied, settings.api_auth_token):
                response = JSONResponse(
                    status_code=401,
                    content={"error": {"code": "authentication_required", "message": "有效的 Bearer token 是必须的"}},
                )
                response.headers["X-Request-ID"] = request_id
                return response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
        )
        return response

    application.add_exception_handler(DomainError, domain_error_handler)
    application.add_exception_handler(TimeoutError, database_error_handler)
    application.add_exception_handler(OSError, database_error_handler)
    application.add_exception_handler(SQLAlchemyError, database_error_handler)
    application.add_exception_handler(ProviderError, provider_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)

    application.include_router(health_router)
    application.include_router(projects_router)
    application.include_router(story_router)
    application.include_router(characters_router)
    application.include_router(world_router)
    application.include_router(plot_router)
    application.include_router(research_router)
    application.include_router(arcs_router)
    application.include_router(chapters_router)
    application.include_router(memory_router)
    application.include_router(automation_router)
    application.include_router(settings_router)
    return application


app = create_app()
