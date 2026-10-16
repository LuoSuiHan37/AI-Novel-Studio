from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

from novel_engine.models.enums import LLMProvider as LLMProviderName
from novel_engine.providers.base import LLMProvider
from novel_engine.providers.types import EmbedResult, GenerateResult, ProviderConfig, StreamChunk, TokenUsage


class ScriptedJsonProvider(LLMProvider):
    def __init__(self, payloads: list[dict]) -> None:
        super().__init__(ProviderConfig(provider=LLMProviderName.OPENAI, model="test-model", api_key="sk-test"))
        self._payloads = payloads
        self.calls = 0

    async def generate(self, messages, *, json_mode: bool = False, temperature: float | None = None) -> GenerateResult:
        payload = self._payloads[min(self.calls, len(self._payloads) - 1)]
        self.calls += 1
        return GenerateResult(
            text=json.dumps(payload),
            usage=TokenUsage(input_tokens=3, output_tokens=7, estimated_cost=0.0, latency_ms=1.0),
            model="test-model",
            provider="openai",
        )

    async def stream(self, messages) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(text="", done=True, usage=TokenUsage())

    async def embed(self, texts: str | Sequence[str]) -> EmbedResult:
        raise AssertionError("embed should not be called")


def editor_payload() -> dict:
    note = {"score": 8, "notes": "ok"}
    return {
        "overall_notes": "Tighten the last line.",
        "needs_human_review": False,
        "pacing": note,
        "dialogue": note,
        "emotion": note,
        "character_voice": note,
        "show_dont_tell": note,
        "repetition": note,
        "grammar": note,
        "hook_strength": note,
        "romantic_tension": note,
        "plot_progress": note,
    }


def approve_payloads(chapter_number: int = 1, hook: str = "Who called her princess?") -> list[dict]:
    return [
        {
            "title": f"Chapter {chapter_number}",
            "summary": f"Chapter {chapter_number} advances the rejection fallout.",
            "key_events": [f"Event {chapter_number}"],
            "new_facts": [f"Fact {chapter_number}"],
            "character_changes": ["Aria remains unranked after the public rejection."],
            "new_secrets": [],
            "resolved_secrets": [],
            "unresolved_hooks": [hook],
            "location": "Moonridge Pack Hall",
        },
        {
            "memories": [
                {
                    "memory_type": "event",
                    "importance": "high",
                    "content": f"Chapter {chapter_number} canon event",
                    "character_name": "Aria",
                }
            ]
        },
        {
            "hooks": [
                {
                    "hook_type": "question",
                    "description": hook,
                    "importance": "high",
                    "setup_chapter_number": chapter_number,
                }
            ],
            "foreshadowings": [
                {
                    "description": "Royal crest burns",
                    "clue_text": "heat under her sternum",
                    "expected_payoff_chapter_number": 12,
                }
            ],
        },
    ]


def generate_payloads() -> list[dict]:
    generation = [
        {
            "title": "The Rejection",
            "prose": ("Kael rejected Aria before the pack. " * 300).strip(),
            "word_count": 1800,
            "used_character_names": ["Aria"],
            "planted_hooks": ["Who called her princess?"],
        },
        {"memories": [], "scene_handoffs": []},
        editor_payload(),
        {"overall": "PASS", "findings": []},
        {"memories": [{"memory_type": "event", "importance": "high", "content": "Kael rejected Aria", "character_name": "Aria"}]},
        {
            "hooks": [
                {
                    "hook_type": "question",
                    "description": "Who called her princess?",
                    "importance": "high",
                    "setup_chapter_number": 1,
                }
            ],
            "foreshadowings": [],
        },
    ]
    # Persisted generation now runs the system audit/commit chain immediately.
    return generation + approve_payloads()
