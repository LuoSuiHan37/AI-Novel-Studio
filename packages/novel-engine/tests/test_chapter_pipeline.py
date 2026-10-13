from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Sequence
from types import SimpleNamespace

import pytest

from novel_engine.domain.errors import InvalidStateError
from novel_engine.memory.service import MemoryService
from novel_engine.models.entities import (
    ChapterPlan,
    Character,
    MasterPlot,
    NovelProject,
    PlotBeat,
    ScenePlan,
    StoryArc,
    StoryBible,
    WorldBible,
    WorldRule,
)
from novel_engine.models.enums import (
    CharacterRole,
    ChapterStatus,
    ContinuityVerdict,
    IntensityLevel,
    LLMProvider as LLMProviderName,
    NarrativeTense,
    PointOfView,
)
from novel_engine.ports.in_memory import InMemoryUnitOfWork
from novel_engine.presets.loader import resolve_style_bundle
from novel_engine.providers.base import LLMProvider
from novel_engine.providers.types import EmbedResult, GenerateResult, ProviderConfig, StreamChunk, TokenUsage
from novel_engine.services.engine import NovelEngine
from novel_engine.style.anti_repetition import StyleHistory, assess_repetition, record_chapter
from novel_engine.agents.contracts import WriterInput
from novel_engine.workflows.agent_workflow import AgentWorkflow
from novel_engine.workflows.chapter_pipeline import ChapterGenerationPipeline
from novel_engine.style.word_count import count_text_units

SKIP_BEAT = "her heart skipped a beat"

CHAPTER_FACTS = {
    1: "Kael rejected Aria Blackwood in the pack hall. Her heart skipped a beat. She walked out with no Luna rank.",
    2: "Aria Blackwood hid in the Blackpine cabin. Her heart skipped a beat when wolves passed. Rank stayed severed.",
    3: "Aria Blackwood took a city alias. Her heart skipped a beat at Kael's scent on the wind. She did not return as Luna.",
    4: "Kael Thorn hunted the forest road. Aria Blackwood sent no word. The rejection still bound pack law.",
    5: "A sealed letter named a public challenge. Aria Blackwood read it at dawn. The cliffhanger is whether she will answer.",
}

STATES = {
    1: "rejected, unranked, leaving the hall",
    2: "hiding in the Blackpine cabin",
    3: "living under a city alias",
    4: "hunted but silent",
    5: "holding a challenge letter",
}


def _cfg() -> ProviderConfig:
    return ProviderConfig(provider=LLMProviderName.OPENAI, model="test-model", api_key="sk-test")


def _editor() -> dict:
    note = {"score": 8, "notes": "ok"}
    return {
        "overall_notes": "Keep the hook.",
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


class RoutingJsonProvider(LLMProvider):
    def __init__(self, *, error_on_chapter: int | None = None, contradiction_chapter: int | None = None) -> None:
        super().__init__(_cfg())
        self.error_on_chapter = error_on_chapter
        self.contradiction_chapter = contradiction_chapter
        self.calls = 0

    async def generate(self, messages, *, json_mode: bool = False, temperature: float | None = None) -> GenerateResult:
        self.calls += 1
        text = " ".join(item.content for item in messages)
        payload = self._payload(text)
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

    def _chapter(self, text: str) -> int:
        match = re.search(r'"chapter_number":\s*(\d+)', text)
        return int(match.group(1)) if match else 1

    def _payload(self, text: str) -> dict:
        number = self._chapter(text)
        if "Chapter Summary Agent" in text:
            return {
                "title": f"Chapter {number}",
                "summary": f"After chapter {number} Aria is {STATES[number]}.",
                "key_events": [CHAPTER_FACTS[number][:80]],
                "new_facts": [STATES[number]],
                "character_changes": [f"Aria Blackwood is {STATES[number]}"],
                "new_secrets": [],
                "resolved_secrets": [],
                "unresolved_hooks": [f"hook-{number}"],
                "location": f"loc-{number}",
            }
        if "Chapter Planner" in text:
            return _plan_payload(number)
        if "Writer Agent" in text:
            prose = CHAPTER_FACTS[number]
            if self.contradiction_chapter == number:
                prose = "Her Luna rank returned overnight. She sat the dais as Luna again."
            return {
                "title": f"Chapter {number}",
                "prose": prose,
                "word_count": len(prose.split()),
                "used_character_names": ["Aria Blackwood", "Kael Thorn"],
                "planted_hooks": [f"hook-{number}"],
            }
        if "Editor Agent" in text:
            return _editor()
        if "Continuity Agent" in text:
            if self.error_on_chapter == number:
                return {
                    "overall": "ERROR",
                    "findings": [
                        {
                            "severity": "ERROR",
                            "category": "world_rule",
                            "problem": "Rank restored illegally",
                            "evidence": "rank returned",
                            "recommendation": "Keep rank severed",
                        }
                    ],
                }
            return {"overall": "PASS", "findings": []}
        if "Memory Agent" in text:
            return {
                "memories": [
                    {
                        "memory_type": "event",
                        "importance": "high",
                        "content": STATES[number],
                        "character_name": "Aria Blackwood",
                    }
                ]
            }
        if "Hook Agent" in text:
            return {
                "hooks": [
                    {
                        "hook_type": "cliffhanger",
                        "description": f"hook-{number}",
                        "importance": "high",
                        "setup_chapter_number": number,
                    }
                ],
                "foreshadowings": [
                    {
                        "description": f"foreshadow-{number}",
                        "clue_text": "crest heat",
                        "expected_payoff_chapter_number": 12,
                    }
                ],
            }
        if "Revise Agent" in text:
            return {
                "prose": "Aria Blackwood remained unranked. The pack law still held.",
                "change_summary": "Removed illegal rank restoration.",
            }
        raise AssertionError(f"unmapped agent prompt: {text[:120]}")


class SceneOverflowProvider(RoutingJsonProvider):
    def __init__(self) -> None:
        super().__init__()
        self.writer_calls = 0

    def _payload(self, text: str) -> dict:
        if "Writer Agent" in text:
            self.writer_calls += 1
            prose = "阿" * (5923 if self.writer_calls == 1 else 2000)
            return {
                "title": "Chapter 1",
                "prose": prose,
                "word_count": len(prose),
                "used_character_names": ["Aria Blackwood"],
                "planted_hooks": ["hook-1"],
            }
        return super()._payload(text)


def _plan_payload(number: int) -> dict:
    return {
        "chapter_number": number,
        "chapter_title": f"Chapter {number}",
        "pov": "Aria Blackwood",
        "location": f"loc-{number}",
        "characters": ["Aria Blackwood"],
        "chapter_goal": "move the plot",
        "conflict": f"conflict-{number}",
        "emotional_arc": "hurt to steel",
        "new_information": f"info-{number}",
        "reveal": "she does not kneel",
        "foreshadowing": "crest",
        "setup": "night",
        "payoff": "choice",
        "cliffhanger": "a letter",
        "scenes": [
            {
                "scene_number": 1,
                "location": f"loc-{number}",
                "characters": ["Aria Blackwood"],
                "goal": "survive",
                "conflict": f"conflict-{number}",
                "turning_point": "she refuses",
                "dialogue_goal": "one cut",
                "emotion": "ice",
                "information_revealed": f"info-{number}",
                "ending": "hook",
            }
        ],
    }


def _character(project_id, name: str, role: CharacterRole) -> Character:
    return Character(
        project_id=project_id,
        name=name,
        role=role,
        personality="proud",
        background="pack blood",
        goal="survive with dignity",
        motivation="never disposable",
        fear="the bond",
        secret="royal blood" if role is CharacterRole.PROTAGONIST else "he still wants her",
        strength="will",
        weakness="pride",
        internal_conflict="love vs revenge",
        external_conflict="pack law",
        speech_style="clipped",
        character_arc="omega to sovereign" if role is CharacterRole.PROTAGONIST else "alpha in doubt",
        tropes=["rejected_mate"],
    )


async def _seed(engine: NovelEngine, chapters: int = 5) -> NovelProject:
    project = await engine.create_project(
        NovelProject(
            title="Moonridge Test Serial",
            genre="werewolf_romance",
            tropes=["rejected_mate"],
            target_platform="alphanovel",
        )
    )
    await engine.story_bibles.upsert(
        StoryBible(
            project_id=project.id,
            premise="Rejected mate returns on her terms.",
            theme="Power after humiliation",
            tone="dark romantic",
            narrative_style="close third serial",
            pov=PointOfView.THIRD_LIMITED,
            tense=NarrativeTense.PAST,
            target_word_count=80_000,
            chapter_word_count=1_800,
            romance_level=IntensityLevel.HIGH,
            tropes=["rejected_mate"],
            logline="She was rejected. The pack will remember.",
            synopsis="Aria is rejected and does not crawl back.",
        )
    )
    await engine.world_bibles.upsert(
        WorldBible(
            project_id=project.id,
            name="Moonridge",
            summary="A mountain pack bound by mate law.",
            geography="Blackpine",
            factions=["Moonridge Pack"],
        )
    )
    await engine.world_bibles.add_rule(
        project.id,
        WorldRule(
            name="Public rejection",
            category="mate_law",
            description="A public rejection severs Luna rank until a public challenge succeeds.",
        ),
    )
    aria = await engine.characters.create(_character(project.id, "Aria Blackwood", CharacterRole.PROTAGONIST))
    kael = await engine.characters.create(_character(project.id, "Kael Thorn", CharacterRole.LOVE_INTEREST))
    await engine.characters.submit_for_review(aria.id)
    await engine.characters.approve(aria.id, confirmed_by="editor")
    await engine.characters.submit_for_review(kael.id)
    await engine.characters.approve(kael.id, confirmed_by="editor")
    plot = await engine.master_plots.create(
        MasterPlot(
            project_id=project.id,
            title="Rejected Luna",
            summary="Rejection, exile, letter, challenge.",
            beats=[
                PlotBeat(name="Rejection", description="Hall", chapter_hint=1),
                PlotBeat(name="Exile", description="Cabin and city", chapter_hint=3),
                PlotBeat(name="Letter", description="Challenge", chapter_hint=5),
            ],
        )
    )
    await engine.story_arcs.create(
        StoryArc(
            project_id=project.id,
            master_plot_id=plot.id,
            title="The Breaking",
            sequence=1,
            summary="From ceremony to the challenge letter.",
            start_chapter_number=1,
            end_chapter_number=5,
        )
    )
    for number in range(1, chapters + 1):
        plan = await engine.chapter_plans.create(
            ChapterPlan(
                project_id=project.id,
                chapter_number=number,
                chapter_title=f"Chapter {number}",
                pov="Aria Blackwood",
                location=f"loc-{number}",
                characters=["Aria Blackwood", "Kael Thorn"],
                chapter_goal=f"goal-{number}",
                conflict=f"conflict-{number}",
                emotional_arc="hurt to steel",
                new_information=f"info-{number}",
                reveal="she does not kneel",
                foreshadowing="crest",
                setup="night",
                payoff="choice",
                cliffhanger="a letter",
            )
        )
        await engine.scene_plans.create(
            ScenePlan(
                chapter_plan_id=plan.id,
                scene_number=1,
                location=f"loc-{number}",
                characters=["Aria Blackwood", "Kael Thorn"],
                goal="survive",
                conflict=f"conflict-{number}",
                turning_point="she refuses",
                dialogue_goal="one cut",
                emotion="ice",
                information_revealed=f"info-{number}",
                ending="hook",
            )
        )
    return project


@pytest.mark.asyncio
async def test_five_chapter_pipeline_memory_and_hitl() -> None:
    engine = NovelEngine(InMemoryUnitOfWork())
    project = await _seed(engine)
    memory = MemoryService()
    pipeline = ChapterGenerationPipeline(
        engine, AgentWorkflow(RoutingJsonProvider()), memory, StyleHistory()
    )

    for number in range(1, 6):
        before = await engine.chapters.get_by_number(project.id, number)
        assert before.status is ChapterStatus.DRAFT
        assert before.content == ""

        loaded = await pipeline.load(project.id, number)
        assert "severs Luna rank" in " ".join(loaded.writer_context.world_rules)
        assert loaded.style.platform.id == "alphanovel"
        if number == 3:
            titles = " ".join(item.summary for item in loaded.package.recent_chapters)
            assert "cabin" in titles
            assert any("severs" in rule.lower() for rule in loaded.package.core_rules)

        draft = await pipeline.draft(project.id, number, persist=True)
        assert draft.advances_next_chapter is False
        assert draft.requires_human_approval is True
        assert draft.chapter.status is ChapterStatus.DRAFT

        assert CHAPTER_FACTS[number] in draft.chapter.content
        if number == 3:
            assert any(item.category == "phrase" and SKIP_BEAT in item.item for item in draft.anti_repetition)

        later = await engine.chapters.list(project.id)
        unfinished = [item for item in later if item.chapter_number > number]
        assert all(item.content == "" and item.status is ChapterStatus.DRAFT for item in unfinished)

        await engine.chapters.mark_reviewed(project.id, number)
        committed = await pipeline.commit_approved_chapter(project.id, number, confirmed_by="editor")
        assert committed.advances_next_chapter is False
        assert committed.chapter.status is ChapterStatus.APPROVED
        assert committed.hooks
        assert committed.foreshadowings
        assert committed.timeline.sequence == number
        aria = next(item for item in committed.character_states if item.name == "Aria Blackwood")
        assert STATES[number] in aria.current_state or STATES[number] in " ".join(aria.experiences)

    chapters = await engine.chapters.list(project.id)
    assert [item.status for item in chapters] == [ChapterStatus.APPROVED] * 5
    assert len(memory.store.timeline_for(project.id)) == 5
    assert memory.store.chapter(project.id, 5) is not None
    hooks = await engine.hooks.list(project.id)
    assert len(hooks) >= 5
    foreshadow = await engine.foreshadowings.list(project.id)
    assert len(foreshadow) >= 5
    six = await engine.chapters.get_by_number(project.id, 5)
    assert six.status is ChapterStatus.APPROVED
    with pytest.raises(InvalidStateError):
        await pipeline.commit_approved_chapter(project.id, 5, confirmed_by="editor")


@pytest.mark.asyncio
async def test_length_normalization_repairs_overlong_chinese_candidate() -> None:
    class LengthRepair:
        async def run(self, _input):
            return SimpleNamespace(output=SimpleNamespace(prose="阿" * 2000))

    class LengthWorkflow:
        revise = LengthRepair()

    engine = NovelEngine(InMemoryUnitOfWork())
    project = await _seed(engine, chapters=1)
    pipeline = ChapterGenerationPipeline(engine, LengthWorkflow(), MemoryService())
    loaded = await pipeline.load(project.id, 1)

    normalized, valid = await pipeline._normalize_length("阿" * 4747, loaded)

    assert valid is True
    assert count_text_units(normalized) == 2000


@pytest.mark.asyncio
async def test_scene_generation_retries_only_overlong_scene_before_assembly() -> None:
    engine = NovelEngine(InMemoryUnitOfWork())
    project = await _seed(engine, chapters=1)
    provider = SceneOverflowProvider()
    workflow = AgentWorkflow(provider)
    pipeline = ChapterGenerationPipeline(engine, workflow, MemoryService())
    loaded = await pipeline.load(project.id, 1)

    bundle = await workflow.draft_chapter_by_scenes(WriterInput(context=loaded.writer_context))

    assert provider.writer_calls == 2
    assert count_text_units(bundle.writer.output.prose) == 2000


@pytest.mark.asyncio
async def test_continuity_error_suggests_revision_without_overwrite() -> None:
    engine = NovelEngine(InMemoryUnitOfWork())
    project = await _seed(engine, chapters=1)
    pipeline = ChapterGenerationPipeline(
        engine,
        AgentWorkflow(RoutingJsonProvider(contradiction_chapter=1)),
        MemoryService(),
    )
    original = await engine.chapters.get_by_number(project.id, 1)
    draft = await pipeline.draft(project.id, 1, persist=False)
    assert draft.continuity.overall is ContinuityVerdict.ERROR
    # Without an independent reviewer, the generation model must not revise
    # its own draft. Only the unreviewed V1 candidate is returned.
    assert draft.revision_suggestion is None
    assert len(draft.versions) == 1
    assert draft.versions[0].score is None
    after = await engine.chapters.get_by_number(project.id, 1)
    assert after.content == original.content == ""


@pytest.mark.asyncio
async def test_human_revision_is_not_overwritten() -> None:
    engine = NovelEngine(InMemoryUnitOfWork())
    project = await _seed(engine, chapters=1)
    pipeline = ChapterGenerationPipeline(engine, AgentWorkflow(RoutingJsonProvider()), MemoryService())
    await pipeline.draft(project.id, 1, persist=True)
    human = "Aria Blackwood wrote this line by hand. The pack did not get a vote."
    await pipeline.persist_revision(
        project.id, 1, human, created_by="studio-user", change_summary="human edit"
    )
    with pytest.raises(InvalidStateError, match="will not be overwritten"):
        await pipeline.draft(project.id, 1, persist=True)
    chapter = await engine.chapters.get_by_number(project.id, 1)
    assert chapter.content == human


def test_platform_preset_is_not_hardcoded_in_core_strings() -> None:
    bundle = resolve_style_bundle(platform_id="alphanovel", novel_id="werewolf_romance")
    assert bundle.platform.chapter_word_min == 1500
    assert bundle.platform.chapter_word_max == 2500
    assert "conflict" in bundle.platform.required_beats
    assert SKIP_BEAT in bundle.platform.monitored_phrases
    source = open(
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "src/novel_engine/workflows/chapter_pipeline.py",
        encoding="utf-8",
    ).read()
    assert "AlphaNovel" not in source
    assert "1500" not in source


def test_anti_repetition_is_frequency_based() -> None:
    history = StyleHistory()
    for number in (1, 2):
        record_chapter(
            history,
            chapter_number=number,
            prose=f"In chapter {number} {SKIP_BEAT} once.",
            location="hall",
            conflict="public shame",
            watchlist=[SKIP_BEAT],
        )
    warnings = assess_repetition(
        prose=f"Again {SKIP_BEAT}.",
        chapter_number=3,
        location="hall",
        conflict="other pressure",
        history=history,
        watchlist=[SKIP_BEAT],
    )
    assert any(item.category == "phrase" for item in warnings)
    banned = assess_repetition(
        prose="She waited in the doorway.",
        chapter_number=4,
        location="city",
        conflict="new fight",
        history=history,
        watchlist=[SKIP_BEAT],
    )
    assert not any(item.item == SKIP_BEAT and item.category == "phrase" for item in banned)
