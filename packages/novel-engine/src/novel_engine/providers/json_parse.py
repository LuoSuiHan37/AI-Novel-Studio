from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from novel_engine.providers.errors import ProviderInvalidResponseError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
TModel = TypeVar("TModel", bound=BaseModel)


def extract_json_object(text: str) -> Any:
    stripped = text.strip()
    fenced = _FENCE_RE.search(stripped)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ProviderInvalidResponseError("response is not valid JSON") from exc
        raise ProviderInvalidResponseError("response is not valid JSON")


def parse_model(schema: type[TModel], payload: Any) -> TModel:
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise ProviderInvalidResponseError(str(exc)) from exc
