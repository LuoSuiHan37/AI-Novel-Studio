from __future__ import annotations

import pytest

from novel_engine.domain.errors import ApprovalRequiredError, DuplicateError, InvalidStateError
from novel_engine.models.entities import (
    ChapterPlan,
    Character,
    Foreshadowing,
    Hook,
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
    ApprovalStatus,
    CharacterRole,
    ForeshadowStatus,
    HookStatus,
    IntensityLevel,
    NarrativeTense,
    PipelineStage,
    PointOfView,
)
from novel_engine.ports.in_memory import InMemoryUnitOfWork
from novel_engine.services.engine import NovelEngine


@pytest.fixture
def engine() -> NovelEngine:
    return NovelEngine(InMemoryUnitOfWork())


async def _project(engine: NovelEngine) -> NovelProject:
    return await engine.create_project(
        NovelProject(title="Moonridge Rejected", tropes=["rejected_mate", "revenge"])
    )


def _bible(project_id) -> StoryBible:
    return StoryBible(
        project_id=project_id,
        premise="A rejected omega returns as hidden royalty.",
        theme="Power reclaimed after public humiliation.",
        tone="dark romantic, high-stakes pack politics",
        narrative_style="close third, sensory, cliffhanger serial",
        pov=PointOfView.THIRD_LIMITED,
        tense=NarrativeTense.PAST,
        target_word_count=80_000,
        chapter_word_count=1_800,
        romance_level=IntensityLevel.HIGH,
        violence_level=IntensityLevel.MEDIUM,
        heat_level=IntensityLevel.MEDIUM,
        tropes=["rejected_mate", "hidden_identity"],
    )


def _character(project_id) -> Character:
    return Character(
        project_id=project_id,
        name="Aria Blackwood",
        role=CharacterRole.PROTAGONIST,
        personality="sharp, proud, slow to trust",
        background="Raised as pack omega after her mother's exile.",
        goal="Make Moonridge kneel without becoming them.",
        motivation="Never again be disposable.",
        fear="That the mate bond still owns her.",
        secret="She carries the old royal bloodline.",
        strength="Political memory and unbreakable will",
        weakness="Pride that delays asking for help",
        internal_conflict="Wants revenge and still loves her fated mate",
        external_conflict="Kael and the council hunt her return",
        speech_style="clipped, formal when angry, rare softness",
        character_arc="From discarded omega to sovereign Luna on her terms",
        tropes=["rejected_mate", "powerful_female_lead"],
    )


def _plan(project_id) -> ChapterPlan:
    return ChapterPlan(
        project_id=project_id,
        chapter_number=1,
        chapter_title="The Rejection",
        pov="Aria",
        location="Moonridge Pack Hall",
        characters=["Aria Blackwood", "Kael Thorn"],
        chapter_goal="Show the public rejection and Aria's unbroken spine.",
        conflict="Kael chooses another Luna before the pack.",
        emotional_arc="humiliation to cold resolve",
        new_information="The council already knew.",
        reveal="Aria does not beg.",
        foreshadowing="A royal crest burns under her skin.",
        setup="Mate ceremony night",
        payoff="She walks out instead of collapsing",
        cliffhanger="A stranger in the woods calls her princess.",
    )


@pytest.mark.asyncio
async def test_planning_stages_do_not_require_manual_approval(engine: NovelEngine) -> None:
    project = await _project(engine)
    project = await engine.pipeline.advance(project.id, confirmed_by="editor")
    assert project.current_stage is PipelineStage.STORY_BIBLE
    bible = await engine.story_bibles.upsert(_bible(project.id))
    assert bible.status is ApprovalStatus.APPROVED
    project = await engine.pipeline.advance(project.id, confirmed_by="editor")
    assert project.current_stage is PipelineStage.WORLD_BIBLE


@pytest.mark.asyncio
async def test_core_planning_pipeline(engine: NovelEngine) -> None:
    project = await _project(engine)
    await engine.pipeline.advance(project.id, confirmed_by="editor")

    bible = await engine.story_bibles.upsert(_bible(project.id))
    await engine.story_bibles.submit_for_review(project.id)
    bible = await engine.story_bibles.approve(project.id, confirmed_by="editor")
    assert bible.status is ApprovalStatus.APPROVED
    edited = await engine.story_bibles.upsert(bible.model_copy(update={"tone": "bleaker"}))
    assert edited.status is ApprovalStatus.APPROVED
    await engine.pipeline.advance(project.id, confirmed_by="editor")

    world = await engine.world_bibles.upsert(
        WorldBible(project_id=project.id, name="Moonridge", summary="A mountain pack bound by mate law.")
    )
    await engine.world_bibles.add_rule(
        project.id,
        WorldRule(name="Rejection is public and binding", category="mate_law", description="A spoken rejection before witnesses severs rank."),
    )
    await engine.world_bibles.submit_for_review(project.id)
    await engine.world_bibles.approve(project.id, confirmed_by="editor")
    await engine.pipeline.advance(project.id, confirmed_by="editor")

    character = await engine.characters.create(_character(project.id))
    with pytest.raises(DuplicateError):
        await engine.characters.create(_character(project.id))
    await engine.characters.submit_for_review(character.id)
    await engine.characters.approve(character.id, confirmed_by="editor")
    await engine.pipeline.advance(project.id, confirmed_by="editor")

    plot = await engine.master_plots.create(
        MasterPlot(
            project_id=project.id,
            title="Rejected Luna Rising",
            summary="Aria is rejected, vanishes, returns as the lost queen.",
            beats=[
                PlotBeat(name="Rejection", description="Public ceremony", chapter_hint=1),
                PlotBeat(name="Exile power", description="She learns the bloodline", chapter_hint=12),
                PlotBeat(name="Return", description="Moonridge kneels", chapter_hint=40),
            ],
        )
    )
    await engine.master_plots.submit_for_review(plot.id)
    await engine.master_plots.approve(plot.id, confirmed_by="editor")

    arc = await engine.story_arcs.create(
        StoryArc(
            project_id=project.id,
            master_plot_id=plot.id,
            title="The Breaking",
            sequence=1,
            summary="From ceremony to the forest road.",
            start_chapter_number=1,
            end_chapter_number=8,
        )
    )
    await engine.story_arcs.submit_for_review(arc.id)
    await engine.story_arcs.approve(arc.id, confirmed_by="editor")
    await engine.pipeline.advance(project.id, confirmed_by="editor")

    plan = await engine.chapter_plans.create(_plan(project.id))
    scene = await engine.scene_plans.create(
        ScenePlan(
            chapter_plan_id=plan.id,
            scene_number=1,
            location="Pack Hall dais",
            characters=["Aria", "Kael"],
            goal="Force the pack to watch her walk away.",
            conflict="Kael needs her to break so the new Luna looks chosen.",
            turning_point="Aria laughs once, then leaves.",
            dialogue_goal="No begging. One line that haunts him.",
            emotion="ice over fire",
            information_revealed="She expected this.",
            ending="She crosses the torchline alone.",
        )
    )
    assert scene.scene_number == 1
    await engine.chapter_plans.submit_for_review(plan.id)
    plan = await engine.chapter_plans.approve(plan.id, confirmed_by="editor")
    forked = await engine.chapter_plans.update(plan.model_copy(update={"cliffhanger": "The stranger knows her true name."}))
    assert forked.version == 1
    assert forked.status is ApprovalStatus.APPROVED
    assert plan.status is ApprovalStatus.APPROVED

    hook = await engine.hooks.create(
        Hook(project_id=project.id, description="Who called Aria princess in the trees?")
    )
    hook = await engine.hooks.plant(hook.id, plan.chapter_id)
    hook = await engine.hooks.activate(hook.id)
    hook = await engine.hooks.resolve(hook.id, plan.chapter_id, confirmed_by="editor")
    assert hook.status is HookStatus.RESOLVED

    seed = await engine.foreshadowings.create(
        Foreshadowing(project_id=project.id, description="Royal crest burns at rejection.")
    )
    seed = await engine.foreshadowings.plant(seed.id, plan.chapter_id)
    seed = await engine.foreshadowings.set_expected_payoff(seed.id, plan.chapter_id)
    seed = await engine.foreshadowings.confirm_payoff(seed.id, plan.chapter_id, confirmed_by="editor")
    assert seed.status is ForeshadowStatus.PAID_OFF

    first = await engine.revisions.save_snapshot(plan.chapter_id, "Kael rejected her before the pack.", change_summary="human draft")
    overlong = await engine.revisions.save_snapshot(plan.chapter_id, "啊" * 3000, change_summary="overlong draft")
    assert overlong.word_count == 3000
    await engine.revisions.save_snapshot(plan.chapter_id, "She did not bow.", change_summary="tighten")
    restored = await engine.revisions.restore(plan.chapter_id, first.id, confirmed_by="editor")
    assert restored.restored_from_revision_id == first.id
    chapter = await engine.uow.chapters.get(plan.chapter_id)
    assert chapter is not None
    assert chapter.content == first.content

    project = await engine.pipeline.advance(project.id, confirmed_by="editor")
    assert project.current_stage is PipelineStage.DRAFTING
