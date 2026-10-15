from __future__ import annotations

import json
from typing import Any

import httpx

from novel_engine.providers.errors import (
    ProviderAuthError,
    ProviderRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


def raise_for_status(response: httpx.Response, *, provider: str) -> None:
    status = response.status_code
    if status in {401, 403}:
        raise ProviderAuthError(f"{provider} authentication failed (HTTP {status})")
    if status == 429:
        raise ProviderRateLimitError(f"{provider} rate limited (HTTP 429)")
    if status >= 400:
        body = _safe_body(response)
        raise ProviderRequestError(
            f"{provider} request failed (HTTP {status}): {body[:500]}"
        )


def map_httpx_error(exc: Exception, *, provider: str) -> None:
    if isinstance(exc, httpx.TimeoutException):
        raise ProviderTimeoutError(f"{provider} request timed out") from exc
    if isinstance(exc, httpx.HTTPError):
        detail = str(exc).strip() or exc.__class__.__name__
        raise ProviderRequestError(f"{provider} HTTP error: {detail}") from exc


def _safe_body(response: httpx.Response) -> str:
    try:
        payload: Any = response.json()
        return json.dumps(payload)
    except Exception:
        return response.text or ""
