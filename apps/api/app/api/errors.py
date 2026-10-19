from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from novel_engine.domain.errors import (
    ApprovalRequiredError,
    DomainError,
    DuplicateError,
    InvalidStateError,
    KnowledgeLeakError,
    NotFoundError,
)
from novel_engine.providers.errors import (
    ProviderAuthError,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnsupportedError,
)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def error_payload(code: str, message: str, request_id: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id} if request_id else {},
    )


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    request_id = _request_id(request)
    mapping: list[tuple[type, str, int]] = [
        (NotFoundError, "not_found", 404),
        (DuplicateError, "conflict", 409),
        (ApprovalRequiredError, "approval_required", 409),
        (KnowledgeLeakError, "knowledge_leak", 422),
        (InvalidStateError, "invalid_state", 422),
    ]
    for cls, code, status in mapping:
        if isinstance(exc, cls):
            return error_payload(code, str(exc), request_id, status)
    return error_payload("domain_error", str(exc), request_id, 400)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _request_id(request)
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    code = "http_error"
    if exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 401:
        code = "unauthorized"
    return error_payload(code, detail, request_id, exc.status_code)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _request_id(request)
    return error_payload("validation_error", str(exc.errors()), request_id, 422)


async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    request_id = _request_id(request)
    if isinstance(exc, ProviderRequestError):
        code = "llm_request_error"
        message = (
            f"LLM 请求失败：{exc}。请检查网络、Base URL、模型名称和 API Key；"
            "如果使用 DeepSeek，请确认 Base URL 为 https://api.deepseek.com/v1。"
        )
    elif isinstance(exc, ProviderInvalidResponseError):
        code = "llm_invalid_response"
        message = (
            f"LLM 返回内容无法按要求解析：{exc}。"
            "请检查模型是否支持 JSON 输出；也可以更换模型后重试。"
        )
    elif isinstance(exc, ProviderRateLimitError):
        code = "llm_rate_limited"
        message = f"LLM 请求被限流：{exc}。请稍后重试或检查 Provider 配额。"
    elif isinstance(exc, ProviderTimeoutError):
        code = "llm_timeout"
        message = f"LLM 请求超时：{exc}。请稍后重试。"
    elif isinstance(exc, ProviderUnsupportedError):
        code = "llm_unsupported"
        message = f"当前 Provider/Model 不支持此操作：{exc}。请更换模型或检查配置。"
    elif isinstance(exc, ProviderAuthError):
        code = "llm_auth_error"
        message = f"LLM 认证失败：{exc}。请打开左侧「AI 设置」检查 Provider、Model、Base URL 和 API Key。"
    else:
        code = "llm_configuration_error"
        message = f"LLM 配置不可用：{exc}。请打开左侧「AI 设置」配置 Provider、Model、Base URL 和 API Key。"
    return error_payload(
        code,
        message,
        request_id,
        422,
    )


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Keep an unavailable database from turning into an opaque 500 traceback."""
    if not isinstance(exc, (SQLAlchemyError, TimeoutError, OSError)):
        raise exc
    return error_payload(
        "database_unavailable",
        "数据库暂时不可用，请确认 PostgreSQL 已启动后重试。",
        _request_id(request),
        503,
    )
