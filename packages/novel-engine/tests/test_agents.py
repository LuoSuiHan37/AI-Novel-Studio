from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import pytest

from novel_engine.agents.continuity import ContinuityAgent
from novel_engine.agents.contracts import (
    ChapterPlannerOutput,
    CharacterAgentOutput,
    ContinuityFinding,
    ContinuityInput,
    ContinuityOutput,
    DimensionNote,
    EditorInput,
    IdeaInput,
    SceneDraft,
    StoryArchitectOutput,
    WriterContext,
    WriterInput,
)
from novel_engine.agents.editor import EditorAgent
from novel_engine.agents.idea import IdeaAgent
from novel_engine.agents.writer import WriterAgent
from novel_engine.domain.errors import InvalidStateError
from novel_engine.models.enums import (
    CharacterRole,
    ContinuityVerdict,
    IntensityLevel,
    LLMProvider as LLMProviderName,
    NarrativeTense,
    PointOfView,
)
from novel_engine.prompts.loader import load_prompt_spec
from novel_engine.providers.base import LLMProvider
from novel_engine.providers.types import EmbedResult, GenerateResult, ProviderConfig, StreamChunk, TokenUsage
from novel_engine.workflows.agent_workflow import AgentWorkflow


def _cfg() -> ProviderConfig:
    return ProviderConfig(provider=LLMProviderName.OPENAI, model="test-model", api_key="sk-test")


class ScriptedJsonProvider(LLMProvider):
    def __init__(self, payloads: list[dict]) -> None:
        super().__init__(_cfg())
        self._payloads = payloads
        self.calls = 0
        self.temperatures: list[float | None] = []

    async def generate(self, messages, *, json_mode: bool = False, temperature: float | None = None) -> GenerateResult:
        self.temperatures.append(temperature)
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


def _bible() -> StoryArchitectOutput:
    return StoryArchitectOutput(
        premise="Rejected omega returns as hidden royalty.",
        theme="Power after humiliation",
        tone="dark romantic",
        narrative_style="close third serial",
        pov=PointOfView.THIRD_LIMITED,
        tense=NarrativeTense.PAST,
        romance_level=IntensityLevel.HIGH,
        violence_level=IntensityLevel.MEDIUM,
        heat_level=IntensityLevel.MEDIUM,
        logline="She was rejected. The pack will remember.",
        synopsis="Aria is rejected, vanishes, and returns as queen.",
    )


def _heroine() -> CharacterAgentOutput:
    return CharacterAgentOutput(
        name="Aria Blackwood",
        role=CharacterRole.PROTAGONIST,
        personality="proud",
        background="exiled bloodline",
        goal="reclaim dignity",
        motivation="never disposable",
        fear="the bond still owns her",
        secret="royal blood",
        strength="will",
        weakness="pride",
        internal_conflict="love vs revenge",
        external_conflict="Kael and the council",
        speech_style="clipped",
        character_arc="omega to sovereign",
        tropes=["rejected_mate"],
    )


def _plan() -> ChapterPlannerOutput:
    return ChapterPlannerOutput(
        chapter_number=1,
        chapter_title="The Rejection",
        pov="Aria Blackwood",
        location="Moonridge Pack Hall",
        characters=["Aria Blackwood"],
        chapter_goal="public rejection",
        conflict="Kael chooses another",
        emotional_arc="humiliation to ice",
        new_information="council knew",
        reveal="she does not beg",
        foreshadowing="crest burns",
        setup="ceremony",
        payoff="she walks out",
        cliffhanger="a stranger says princess",
        scenes=[
            SceneDraft(
                scene_number=1,
                location="dais",
                characters=["Aria Blackwood"],
                goal="leave unbroken",
                conflict="pack watches",
                turning_point="she laughs",
                dialogue_goal="one cutting line",
                emotion="ice",
                information_revealed="she expected it",
                ending="she crosses the torches",
            )
        ],
    )


def _context() -> WriterContext:
    return WriterContext(
        story_bible=_bible(),
        world_rules=["Public rejection severs rank."],
        characters=[_heroine()],
        chapter_plan=_plan(),
        open_hooks=[],
        memories=[],
        constraints=["Do not rename Aria."],
    )


def _note(score: int = 8) -> DimensionNote:
    return DimensionNote(score=score, notes="ok")


def _editor_payload() -> dict:
    note = _note().model_dump()
    return {
        "overall_notes": "Tighten the last line.",
        "needs_human_review": True,
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


def test_prompt_spec_metadata() -> None:
    spec = load_prompt_spec("agents/idea.yaml")
    assert spec.id == "idea"
    assert spec.version == "1.1.0"
    assert spec.temperature == 0.85
    assert "tropes" in spec.variables
    assert "You are the Idea Agent" in spec.system


def test_writer_prompt_version_and_alias_guidance() -> None:
    spec = load_prompt_spec("agents/writer.yaml")
    assert spec.version == "1.6.0"
    assert "formal names or aliases" in spec.system


def test_all_agents_inherit_fanqie_content_safety_policy() -> None:
    spec = load_prompt_spec("agents/writer.yaml")
    assert spec.version == "1.6.0"
    assert "\u756a\u8304\u5c0f\u8bf4\u5185\u5bb9\u5b89\u5168\u987b\u77e5" in spec.system
    assert "\u672a\u6210\u5e74\u4eba\u8d1f\u9762\u5bfc\u5411" in spec.system
    assert "\u53d1\u73b0\u98ce\u9669\u65f6\u505c\u6b62\u6269\u5199" in spec.system


@pytest.mark.asyncio
async def test_idea_agent_uses_schema_not_free_text() -> None:
    provider = ScriptedJsonProvider(
        [
            {
                "working_title": "Rejected Luna",
                "logline": "She was rejected before the pack.",
                "premise": "Hidden royalty returns.",
                "theme": "Identity after betrayal",
                "synopsis": "After a public rejection, a hidden heir returns to challenge the pack that cast her out.",
                "tropes": ["rejected_mate"],
                "series_hooks": ["Who called her princess?"],
                "risks": ["Mate bond cliche"],
            }
        ]
    )
    result = await IdeaAgent(provider).run(
        IdeaInput(tropes=["rejected_mate"], brief="Public rejection, then revenge.", platform="alphanovel")
    )
    assert result.prompt_version == "1.1.0"
    assert result.temperature == 0.85
    assert result.output.working_title == "Rejected Luna"
    assert result.output.synopsis.startswith("After a public rejection")
    assert provider.temperatures == [0.85]


@pytest.mark.asyncio
async def test_writer_requires_external_context() -> None:
    writer = WriterAgent(ScriptedJsonProvider([{}]))
    empty = WriterContext(
        story_bible=_bible(),
        world_rules=["rule"],
        characters=[],
        chapter_plan=_plan(),
    )
    with pytest.raises(InvalidStateError, match="characters"):
        await writer.run(WriterInput(context=empty))


@pytest.mark.asyncio
async def test_writer_rejects_invented_characters() -> None:
    provider = ScriptedJsonProvider(
        [
            {
                "title": "The Rejection",
                "prose": "A stranger named Wolf King appeared.",
                "word_count": 6,
                "used_character_names": ["Wolf King"],
                "planted_hooks": [],
            }
        ]
    )
    with pytest.raises(InvalidStateError, match="invented"):
        await WriterAgent(provider).run(WriterInput(context=_context()))


@pytest.mark.asyncio
async def test_writer_accepts_character_aliases() -> None:
    context = _context().model_copy(
        update={
            "characters": [_heroine().model_copy(update={"aliases": ["阿莉娅"]})],
        }
    )
    provider = ScriptedJsonProvider(
        [
            {
                "title": "The Rejection",
                "prose": "阿莉娅走过火炬。",
                "word_count": 8,
                "used_character_names": ["阿莉娅"],
                "planted_hooks": [],
            }
        ]
    )
    result = await WriterAgent(provider).run(WriterInput(context=context))
    assert result.output.used_character_names == ["阿莉娅"]
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_writer_automatically_repairs_unknown_characters() -> None:
    provider = ScriptedJsonProvider(
        [
            {
                "title": "The Rejection",
                "prose": "A stranger named Wolf King appeared.",
                "word_count": 6,
                "used_character_names": ["Wolf King"],
                "planted_hooks": [],
            },
            {
                "title": "The Rejection",
                "prose": "Aria crossed the torches.",
                "word_count": 5,
                "used_character_names": ["Aria Blackwood"],
                "planted_hooks": [],
            },
        ]
    )
    result = await WriterAgent(provider).run(WriterInput(context=_context()))
    assert result.output.used_character_names == ["Aria Blackwood"]
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_continuity_error_roll_up() -> None:
    provider = ScriptedJsonProvider(
        [
            ContinuityOutput(
                overall=ContinuityVerdict.PASS,
                findings=[
                    ContinuityFinding(
                        severity=ContinuityVerdict.ERROR,
                        category="character",
                        problem="Aria's rank changed without setup",
                        evidence="She is called Luna before the return arc",
                        recommendation="Keep her as rejected omega in ch1",
                    )
                ],
            ).model_dump()
        ]
    )
    result = await ContinuityAgent(provider).run(
        ContinuityInput(context=_context(), prose="They called her Luna.")
    )
    assert result.output.overall is ContinuityVerdict.ERROR
    assert result.output.findings[0].category == "character"
    assert result.output.findings[0].evidence


@pytest.mark.asyncio
async def test_editor_covers_required_dimensions() -> None:
    result = await EditorAgent(ScriptedJsonProvider([_editor_payload()])).run(
        EditorInput(context=_context(), prose="Kael rejected Aria.")
    )
    for name in (
        "pacing",
        "dialogue",
        "emotion",
        "character_voice",
        "show_dont_tell",
        "repetition",
        "grammar",
        "hook_strength",
        "romantic_tension",
        "plot_progress",
    ):
        assert getattr(result.output, name).score >= 1


@pytest.mark.asyncio
async def test_workflow_schedules_agents_without_agent_to_agent_calls() -> None:
    writer_json = {
        "title": "The Rejection",
        "prose": "Kael rejected Aria before the pack.",
        "word_count": 7,
        "used_character_names": ["Aria Blackwood"],
        "planted_hooks": ["stranger in the woods"],
    }
    continuity_json = ContinuityOutput(overall=ContinuityVerdict.PASS, findings=[]).model_dump()
    memory_json = {"memories": [{"memory_type": "event", "importance": "critical", "content": "Public rejection", "character_name": "Aria Blackwood"}]}
    hook_json = {
        "hooks": [
            {
                "hook_type": "cliffhanger",
                "description": "Who called her princess?",
                "importance": "high",
                "setup_chapter_number": 1,
            }
        ],
        "foreshadowings": [
            {
                "description": "Royal crest burns",
                "clue_text": "heat under her sternum",
                "expected_payoff_chapter_number": 12,
            }
        ],
    }
    provider = ScriptedJsonProvider([writer_json, _editor_payload(), continuity_json, memory_json, hook_json])
    workflow = AgentWorkflow(provider)
    assert not hasattr(workflow.writer, "editor")
    assert workflow.editor.__class__ is EditorAgent
    bundle = await workflow.draft_chapter_pass(WriterInput(context=_context()))
    assert provider.calls == 5
    assert bundle.writer.output.prose.startswith("Kael")
    assert bundle.continuity.output.overall is ContinuityVerdict.PASS
    assert bundle.memory.output.memories[0].content
    assert bundle.hooks.output.hooks[0].description
