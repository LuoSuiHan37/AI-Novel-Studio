from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar

from pydantic import BaseModel

from novel_engine.prompts.loader import PromptSpec, dump_prompt_value, load_prompt_spec
from novel_engine.providers.base import LLMProvider
from novel_engine.providers.types import ChatMessage, TokenUsage

TIn = TypeVar("TIn", bound=BaseModel)
TOut = TypeVar("TOut", bound=BaseModel)


class AgentResult(BaseModel, Generic[TOut]):
    agent: str
    prompt_id: str
    prompt_version: str
    temperature: float
    provider: str | None = None
    model: str | None = None
    output: TOut
    usage: TokenUsage


class BaseAgent(ABC, Generic[TIn, TOut]):
    """LLM proposal agent. Must not persist state or call other agents."""

    name: str
    prompt_file: str
    input_model: type[TIn]
    output_model: type[TOut]

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        if self.__class__ is BaseAgent:
            raise TypeError("BaseAgent cannot be used directly")

    def load_prompt(self) -> PromptSpec:
        return load_prompt_spec(self.prompt_file)

    async def run(self, payload: TIn) -> AgentResult[TOut]:
        spec = self.load_prompt()
        values = _variable_map(payload, spec)
        system, user = spec.render(values)
        parsed, raw = await self._provider.generate_json(
            [
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=user),
            ],
            self.output_model,
            temperature=spec.temperature,
        )
        return AgentResult(
            agent=self.name,
            prompt_id=spec.id,
            prompt_version=spec.version,
            temperature=spec.temperature,
            provider=spec.provider.value if spec.provider else None,
            model=spec.model,
            output=parsed,
            usage=raw.usage,
        )


def _variable_map(payload: BaseModel, spec: PromptSpec) -> dict[str, str]:
    data = payload.model_dump()
    values = {name: dump_prompt_value(data.get(name)) for name in spec.variables}
    values.setdefault("input_json", payload.model_dump_json(indent=2))
    return values
