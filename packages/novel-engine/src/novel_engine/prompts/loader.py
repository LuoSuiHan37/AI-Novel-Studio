from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from novel_engine.models.enums import LLMProvider as LLMProviderName

_PLACEHOLDER_PREFIX = "{{"
_PLACEHOLDER_SUFFIX = "}}"


class PromptSpec(BaseModel):
    """Versioned prompt document. Body lives in YAML, not in Python."""

    model_config = ConfigDict(extra="ignore")

    id: str
    version: str
    temperature: float = 0.7
    provider: LLMProviderName | None = None
    model: str | None = None
    variables: list[str] = Field(default_factory=list)
    system: str
    user: str

    def render(self, values: dict[str, str]) -> tuple[str, str]:
        missing = [name for name in self.variables if name not in values]
        if missing:
            raise KeyError(f"prompt {self.id} missing variables: {', '.join(missing)}")
        return render_prompt(self.system, **values), render_prompt(self.user, **values)


def prompts_root() -> Path:
    env_dir = os.environ.get("NOVEL_ENGINE_PROMPTS_DIR")
    if env_dir:
        return Path(env_dir)
    here = Path(__file__).resolve()
    repo_prompts = here.parents[5] / "prompts"
    if repo_prompts.is_dir():
        return repo_prompts
    cwd_prompts = Path.cwd() / "prompts"
    if cwd_prompts.is_dir():
        return cwd_prompts
    raise FileNotFoundError(
        "Prompt directory not found. Set NOVEL_ENGINE_PROMPTS_DIR or run from the repo root."
    )


def agent_prompts_root() -> Path:
    env_dir = os.environ.get("NOVEL_ENGINE_AGENT_PROMPTS_DIR")
    if env_dir:
        return Path(env_dir)
    package_prompts = Path(__file__).resolve().parents[3] / "prompts"
    if package_prompts.is_dir():
        return package_prompts
    raise FileNotFoundError(
        "Agent prompt directory not found. Set NOVEL_ENGINE_AGENT_PROMPTS_DIR "
        "or keep packages/novel-engine/prompts on disk."
    )


def load_prompt(relative_path: str) -> str:
    path = prompts_root() / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Prompt asset missing: {path}")
    return path.read_text(encoding="utf-8")


def load_prompt_spec(relative_path: str) -> PromptSpec:
    path = agent_prompts_root() / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Agent prompt missing: {path}")
    payload: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    spec = PromptSpec.model_validate(payload)
    # Every agent inherits the platform safety boundary from an auditable
    # prompt asset instead of hard-coded policy text in Python business logic.
    policy_path = agent_prompts_root() / "policies" / "fanqie_content_safety.txt"
    if policy_path.is_file():
        policy = policy_path.read_text(encoding="utf-8").strip()
        spec = spec.model_copy(update={"system": f"{spec.system.rstrip()}\n\n{policy}"})
    return spec


def render_prompt(template: str, **values: str) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{_PLACEHOLDER_PREFIX}{key}{_PLACEHOLDER_SUFFIX}", value)
    return rendered


def dump_prompt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, BaseModel):
        return value.model_dump_json(indent=2)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(value)
