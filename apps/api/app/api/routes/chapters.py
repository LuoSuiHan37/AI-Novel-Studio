from __future__ import annotations

from difflib import SequenceMatcher
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.memory_bridge import hydrate_pipeline_memory, persist_commit
from app.api.context_builder import build_writer_context
from app.api.deps import (
    Actor,
    confirmed_by,
    get_actor,
    get_engine,
    get_llm_provider,
    get_review_workflow,
    get_workflow,
)
from app.api.schemas import ChapterPatch, ChapterPlanCreate, ChapterPlanSuggest, ConfirmBody, GenerateBody, ProposeEditBody
from app.services.book_snapshot import save_project_snapshot
from app.db.models.chapter import ChapterSummary
from app.db.models.continuity import ContinuityIssue
from novel_engine.agents.contracts import (
    ChapterPlannerInput,
    CommercialReviewInput,
    ContinuityOutput,
    ContinuityInput,
    EditorInput,
    OutlineOutput,
    ReviseInput,
)
from novel_engine.domain.errors import InvalidStateError
from novel_engine.memory.service import MemoryService
from novel_engine.models.entities import ChapterPlan, Hook, ScenePlan
from novel_engine.models.enums import ApprovalStatus, ChapterStatus, ContinuitySeverity, ContinuityVerdict
from novel_engine.presets.loader import resolve_style_bundle
from novel_engine.providers.base import LLMProvider
from novel_engine.providers.types import ChatMessage
from novel_engine.services.engine import NovelEngine
from novel_engine.workflows.agent_workflow import AgentWorkflow
from novel_engine.workflows.chapter_pipeline import ChapterGenerationPipeline, is_local_revision
from novel_engine.workflows.context import character_to_agent, plot_to_outline, story_bible_to_architect
from novel_engine.style.canon import scan_context_alignment
from novel_engine.style.commercial import scan_commercial_quality
from novel_engine.style.chapter_repetition import scan_book_repetition, scan_chapter_repetition
from novel_engine.style.chapter_relevance import scan_chapter_relevance
from novel_engine.style.signals import scan_continuity_signals
from novel_engine.agents.contracts import ChapterPlannerInput, ContinuityInput, EditorInput, OutlineOutput, ReviseInput
from novel_engine.workflows.context import character_to_agent, plot_to_outline, story_bible_to_architect

router = APIRouter(tags=["chapters"])


def _apply_chapter_budgets(proposal, *, minimum: int, maximum: int):
    """Give the UI a concrete budget even when a model omits optional fields."""
    scenes = list(proposal.scenes)
    if not scenes:
        return proposal
    target = proposal.target_word_count or round((minimum + maximum) / 2)
    target = min(target, maximum - 150)
    target = max(minimum + 100, target)
    base, remainder = divmod(target, len(scenes))
    planned = []
    for index, scene in enumerate(scenes):
        words = base + (1 if index < remainder else 0)
        planned.append(scene.model_copy(update={
            "target_word_count": words,
            "target_word_min": max(1, words - 80),
            "target_word_max": words + 80,
        }))
    return proposal.model_copy(update={
        "target_word_count": target,
        "target_word_min": minimum,
        "target_word_max": maximum,
        "scenes": planned,
    })


class ChapterTitleSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str


@router.get("/projects/{project_id}/chapters")
async def list_chapters(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    return await engine.chapters.list(project_id)


@router.get("/projects/{project_id}/chapters/repetition-scan")
async def repetition_scan(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    """Run the full-book duplicate scan used before export/publishing."""

    chapters = await engine.chapters.list(project_id)
    findings = scan_book_repetition(chapters)
    return {"status": "blocked" if findings else "passed", "findings": findings}


@router.get("/projects/{project_id}/audit")
async def novel_audit(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    """Run the complete pre-publish audit for the whole novel."""
    project = await engine.get_project(project_id)
    chapters = sorted(await engine.chapters.list(project_id), key=lambda item: item.chapter_number)
    story = await engine.story_bibles.get(project_id)
    world = await engine.world_bibles.get(project_id)
    plots = await engine.master_plots.list(project_id)
    arcs = await engine.story_arcs.list(project_id)
    active_plot = next((item for item in plots if item.is_active), plots[0] if plots else None)
    missing_architecture: list[str] = []
    if story is None:
        missing_architecture.append("story_bible")
    elif story.status is not ApprovalStatus.APPROVED:
        missing_architecture.append("story_bible_not_approved")
    if world is None:
        missing_architecture.append("world_bible")
    elif world.status is not ApprovalStatus.APPROVED:
        missing_architecture.append("world_bible_not_approved")
    if active_plot is None:
        missing_architecture.append("master_plot")
    elif active_plot.status is not ApprovalStatus.APPROVED:
        missing_architecture.append("master_plot_not_approved")
    if not arcs:
        missing_architecture.append("story_arcs")
    elif any(item.status is not ApprovalStatus.APPROVED for item in arcs):
        missing_architecture.append("story_arcs_not_approved")
    characters = await engine.characters.list(project_id)
    if not characters:
        missing_architecture.append("characters")
    elif any(item.status is not ApprovalStatus.APPROVED for item in characters):
        missing_architecture.append("characters_not_approved")
    if active_plot is not None:
        if len(active_plot.beats) < 3:
            missing_architecture.append("master_plot_beats")
        if target := project.chapter_count_target:
            hints = [beat.chapter_hint for beat in active_plot.beats if beat.chapter_hint is not None]
            if hints and (min(hints) < 1 or max(hints) > target):
                missing_architecture.append("master_plot_beat_range")
    if target := project.chapter_count_target:
        covered = [
            number
            for number in range(1, target + 1)
            if any(
                (arc.start_chapter_number or 1) <= number <= (arc.end_chapter_number or target)
                for arc in arcs
            )
        ]
        if len(covered) != target:
            missing_architecture.append("story_arc_coverage")
    target = project.chapter_count_target
    numbers = {item.chapter_number for item in chapters}
    missing = [number for number in range(1, target + 1) if number not in numbers] if target else []
    overflow = sorted(number for number in numbers if target and number > target)
    empty = [item.chapter_number for item in chapters if not item.content.strip()]
    unfinished = [
        item.chapter_number for item in chapters
        if item.status.value not in {"approved", "published"}
    ]
    repetition_findings = scan_book_repetition(chapters)
    relevance_findings: list[dict] = []
    missing_plans: list[int] = []
    for chapter in chapters:
        plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
        if plan is None:
            missing_plans.append(chapter.chapter_number)
            continue
        scenes = await engine.scene_plans.list(plan.id)
        relevance = scan_chapter_relevance(content=chapter.content, plan=plan, scenes=scenes)
        if relevance.blocked:
            relevance_findings.append({
                "chapter_number": chapter.chapter_number,
                **relevance.model_dump(),
            })
    blocked = bool(
        missing
        or overflow
        or empty
        or unfinished
        or repetition_findings
        or relevance_findings
        or missing_plans
        or missing_architecture
    )
    return {
        "status": "blocked" if blocked else "passed",
        "publishable": not blocked,
        "planned_chapter_count": target,
        "actual_chapter_count": len(chapters),
        "missing_chapters": missing,
        "overflow_chapters": overflow,
        "empty_chapters": empty,
        "unfinished_chapters": unfinished,
        "missing_plans": missing_plans,
        "missing_architecture": missing_architecture,
        "repetition_findings": repetition_findings,
        "relevance_findings": relevance_findings,
    }


@router.post("/projects/{project_id}/chapters/title-suggestion")
async def suggest_chapter_title(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> dict[str, str]:
    project = await engine.get_project(project_id)
    chapters = sorted(
        await engine.chapters.list(project_id),
        key=lambda item: item.chapter_number,
    )
    next_number = (chapters[-1].chapter_number + 1) if chapters else 1
    previous = chapters[-1] if chapters else None
    story = await engine.story_bibles.get(project_id)
    plot_items = await engine.master_plots.list(project_id)
    active_plot = next((item for item in plot_items if item.is_active), None)

    previous_context = "No previous chapter."
    if previous:
        previous_context = (
            f"Previous title: {previous.title}.\n"
            f"Previous chapter text excerpt: {previous.content[-2500:] or '(empty)'}"
        )
    story_context = (
        f"Premise: {story.premise}\nTheme: {story.theme}\nSynopsis: {story.synopsis or ''}"
        if story
        else "Story bible has not been written yet."
    )
    plot_context = active_plot.summary if active_plot else "No master plot is available yet."

    result, _ = await provider.generate_json(
        [
            ChatMessage(
                role="system",
                content=(
                    "You are a fiction editor naming a chapter. Create one concise, memorable "
                    "chapter title in the same language and style as the novel. Use the supplied "
                    f"story and previous chapter context. The novel output language is {project.language}; "
                    "write the title entirely in that language. Return only the requested JSON."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    f"Novel title: {project.title}\nGenre: {project.genre}\n"
                    f"Next chapter number: {next_number}\n{story_context}\n"
                    f"Plot outline: {plot_context}\n{previous_context}\n"
                    "Generate an apt title for the next chapter. The title should not simply be "
                    "'Chapter N'."
                ),
            ),
        ],
        ChapterTitleSuggestion,
        temperature=0.8,
    )
    title = result.title.strip().strip("\"'“”‘’")
    if not title:
        raise InvalidStateError("the model returned an empty chapter title")
    return {"title": title}


@router.post("/projects/{project_id}/chapters/plan", status_code=status.HTTP_201_CREATED)
async def create_chapter_plan(
    project_id: UUID,
    body: ChapterPlanCreate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    if not body.scenes:
        raise InvalidStateError("chapter plan must contain at least one scene")
    plan = await engine.chapter_plans.create(
        ChapterPlan(
            project_id=project_id,
            chapter_number=body.chapter_number,
            chapter_title=body.chapter_title,
            pov=body.pov,
            location=body.location,
            characters=body.characters,
            chapter_goal=body.chapter_goal,
            conflict=body.conflict,
            emotional_arc=body.emotional_arc,
            new_information=body.new_information,
            reveal=body.reveal,
            foreshadowing=body.foreshadowing,
            setup=body.setup,
            payoff=body.payoff,
            cliffhanger=body.cliffhanger,
            target_word_count=body.target_word_count or 0,
            target_word_min=body.target_word_min or 0,
            target_word_max=body.target_word_max or 0,
        )
    )
    scenes = []
    for item in body.scenes:
        scenes.append(
            await engine.scene_plans.create(
                ScenePlan(
                    chapter_plan_id=plan.id,
                    **item.model_dump(exclude_none=True),
                )
            )
        )
    chapter = await engine.chapters.get_by_number(project_id, body.chapter_number)
    await save_project_snapshot(engine, project_id)
    return {"plan": plan, "scenes": scenes, "chapter": chapter}


@router.post("/projects/{project_id}/chapters/plan-suggestion")
async def suggest_chapter_plan(
    project_id: UUID,
    body: ChapterPlanSuggest,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
):
    project = await engine.get_project(project_id)
    bible = await engine.story_bibles.get(project_id)
    if bible is None:
        raise InvalidStateError("请先完善小说简介，再生成章节计划")

    plots = await engine.master_plots.list(project_id)
    plot = next((item for item in plots if item.is_active), plots[0] if plots else None)
    arcs = await engine.story_arcs.list(project_id)
    if plot:
        outline = plot_to_outline(plot, arcs)
    else:
        outline = OutlineOutput(
            title=project.title,
            structure="serial",
            summary=bible.premise,
            beats=[],
            arcs=[],
        )
    arc = next(
        (
            item for item in arcs
            if (item.start_chapter_number is None or item.start_chapter_number <= body.chapter_number)
            and (item.end_chapter_number is None or item.end_chapter_number >= body.chapter_number)
        ),
        None,
    )
    if arc is None:
        arc = next((item for item in arcs if item.status.value == "approved"), arcs[0] if arcs else None)

    previous_summary = None
    previous_chapters = [
        item for item in await engine.chapters.list(project_id)
        if item.chapter_number < body.chapter_number
    ]
    previous_chapter = max(previous_chapters, key=lambda item: item.chapter_number, default=None)
    if previous_chapter:
        session = getattr(engine.uow, "session", None)
        summary_row = None
        if isinstance(session, AsyncSession):
            summary_row = await session.scalar(
                select(ChapterSummary).where(ChapterSummary.chapter_id == previous_chapter.id)
            )
        if summary_row:
            previous_summary = (
                f"Chapter {previous_chapter.chapter_number}, {previous_chapter.title}: "
                f"{summary_row.summary} Key events: {', '.join(summary_row.key_events or [])}"
            )
        else:
            revisions = await engine.revisions.list(previous_chapter.id)
            previous_text = revisions[-1].content if revisions else previous_chapter.content
            previous_summary = (
                f"Chapter {previous_chapter.chapter_number}, {previous_chapter.title}. "
                f"Recent text: {previous_text[-3500:]}"
            )

    style = resolve_style_bundle(
        platform_id=project.target_platform,
        novel_id=project.genre,
        language=project.language,
    )
    creative_profile = (project.extra_metadata or {}).get("creative_profile", {})
    profile_style = creative_profile.get("style_guide", "") if isinstance(creative_profile, dict) else ""
    if profile_style:
        style = style.model_copy(update={"style_guide": f"{style.style_guide}\n{profile_style}"})
    world = await engine.world_bibles.get(project_id)
    open_hooks = await engine.hooks.list(project_id, open_only=True)
    proposal = await workflow.propose_chapter_plan(
        ChapterPlannerInput(
            story_bible=story_bible_to_architect(bible),
            outline=outline,
            characters=[character_to_agent(item) for item in await engine.characters.list(project_id)],
            chapter_number=body.chapter_number,
            previous_chapter_summary=previous_summary,
            style_guide=style.style_guide,
            current_arc=arc.summary if arc else "",
            world_rules=[rule.description for rule in (world.rules if world else [])],
            open_hooks=[item.description for item in open_hooks],
            language=project.language,
            creative_profile=creative_profile,
        )
    )
    if not proposal.output.scenes or not proposal.output.characters:
        raise InvalidStateError("AI 章节计划必须包含角色和至少一个场景，请重试或完善角色设定")
    return _apply_chapter_budgets(
        proposal.output,
        minimum=style.platform.chapter_word_min,
        maximum=style.platform.chapter_word_max,
    )


@router.post("/projects/{project_id}/chapters/{number}/generate")
async def generate_chapter(
    project_id: UUID,
    number: int,
    body: GenerateBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    actor: Annotated[Actor, Depends(get_actor)],
    review_workflow: Annotated[AgentWorkflow | None, Depends(get_review_workflow)],
) -> dict:
    pipeline = await _pipeline(engine, workflow, project_id, review_workflow=review_workflow)
    result = await pipeline.draft(
        project_id,
        number,
        human_notes=body.human_notes,
        generate_scenes=body.generate_scenes,
        persist=body.persist,
        overwrite_human=body.overwrite_human,
        created_by=actor.id,
    )
    if body.persist:
        chapter_row = await engine.chapters.get_by_number(project_id, number)
        metadata = dict(chapter_row.extra_metadata or {})
        commercial = result.secondary_commercial
        commercial_blocked = review_workflow is not None and (
            commercial is None
            or commercial.needs_human_review
            or commercial.reader_pressure_score < 6
            or commercial.reader_promise_score < 6
            or commercial.rhythm_score < 6
            or commercial.ai_style_risk_score < 5
        )
        metadata["audit"] = {
            "status": (
                "completed_with_errors"
                if result.continuity.overall is ContinuityVerdict.ERROR
                or result.bundle.editor.output.needs_human_review
                or commercial_blocked
                else "completed" if review_workflow is not None else "not_configured"
            ),
            "versions": [item.model_dump() for item in result.versions],
            "repetition_check": result.repetition_check,
            "relevance_check": result.relevance_check,
            "independent_review": getattr(review_workflow, "provider_identity", None),
            "independent_commercial": commercial.model_dump() if commercial else None,
        }
        await engine.chapters.update(chapter_row.model_copy(update={"extra_metadata": metadata}))
        await save_project_snapshot(engine, project_id)
    auto_approved = False
    if (
        body.persist
        and review_workflow is not None
        and result.continuity.overall is not ContinuityVerdict.ERROR
        and not result.repetition_check.get("blocked", False)
        and not result.relevance_check.get("blocked", False)
        and not result.bundle.editor.output.needs_human_review
        and not commercial_blocked
    ):
        # Automatic mode keeps the same audit gates but records the approval
        # as a system action instead of waiting for a UI confirmation click.
        await engine.chapters.mark_reviewed(project_id, number)
        pipeline_result = await pipeline.commit_approved_chapter(
            project_id,
            number,
            confirmed_by="system-auto",
        )
        session = getattr(engine.uow, "session", None)
        if isinstance(session, AsyncSession):
            await persist_commit(session, project_id, pipeline_result.chapter.id, pipeline, pipeline_result)
        chapter_row = await engine.chapters.get_by_number(project_id, number)
        await save_project_snapshot(engine, project_id)
        auto_approved = chapter_row.status is ChapterStatus.APPROVED
    else:
        chapter_row = await engine.chapters.get_by_number(project_id, number)
    writer = result.bundle.writer.output
    return {
        "chapter": chapter_row,
        "revision": result.persisted_revision,
        "writer": writer,
        "editor": result.bundle.editor.output,
        "continuity": result.continuity,
        "secondary_continuity": result.secondary_continuity,
        "secondary_commercial": result.secondary_commercial,
        "versions": result.versions,
        "independent_review_available": review_workflow is not None,
        "review_status": (
            "not_configured"
            if review_workflow is None
            else "completed_with_errors"
            if result.continuity.overall is ContinuityVerdict.ERROR
            or result.bundle.editor.output.needs_human_review
            or (
                review_workflow is not None
                and (
                    result.secondary_commercial is None
                    or result.secondary_commercial.needs_human_review
                    or result.secondary_commercial.reader_pressure_score < 6
                    or result.secondary_commercial.reader_promise_score < 6
                    or result.secondary_commercial.rhythm_score < 6
                    or result.secondary_commercial.ai_style_risk_score < 5
                )
            )
            else "completed"
        ),
        "memory_proposals": result.bundle.memory.output,
        "hook_proposals": result.bundle.hooks.output,
        "revision_suggestion": result.revision_suggestion,
        "anti_repetition": result.anti_repetition,
        "repetition_check": result.repetition_check,
        "relevance_check": result.relevance_check,
        "length_ok": result.length_ok,
        "length_warning": result.length_warning,
        "persisted": body.persist,
        "requires_human_approval": False,
        "auto_approved": auto_approved,
        "advances_next_chapter": False,
    }


@router.post("/projects/{project_id}/chapters/{number}/propose-edit")
async def propose_edit(
    project_id: UUID,
    number: int,
    body: ProposeEditBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    actor: Annotated[Actor, Depends(get_actor)],
    review_workflow: Annotated[AgentWorkflow | None, Depends(get_review_workflow)],
) -> dict:
    await engine.chapters.get_by_number(project_id, number)
    if body.persist and review_workflow is None:
        raise InvalidStateError("请先配置独立审查模型，不能保存未经独立审查的 AI 改稿")
    result = await workflow.revise.run(
        ReviseInput(instruction=body.instruction, source_prose=body.source_prose)
    )
    similarity = SequenceMatcher(None, body.source_prose, result.output.prose).ratio()
    accepted = is_local_revision(body.source_prose, result.output.prose, similarity)
    revision = None
    if body.persist and accepted:
        pipeline = await _pipeline(engine, workflow, project_id)
        revision = await pipeline.persist_revision(
            project_id,
            number,
            result.output.prose,
            created_by=actor.id,
            change_summary=result.output.change_summary or "revise-agent",
        )
    return {
        "prose": result.output.prose,
        "change_summary": result.output.change_summary,
        "revision": revision,
        "persisted": bool(body.persist and accepted),
        "accepted": accepted,
        "rejection_reason": None if accepted else "AI output rewrote too much or was truncated; original text was preserved",
        "similarity": round(similarity, 4),
    }


@router.get("/projects/{project_id}/chapters/{number}")
async def get_chapter(
    project_id: UUID,
    number: int,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    chapter = await engine.chapters.get_by_number(project_id, number)
    plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
    scenes = await engine.scene_plans.list(plan.id) if plan else []
    if plan and scenes and not any(scene.target_word_count for scene in scenes):
        project = await engine.get_project(project_id)
        style = resolve_style_bundle(
            platform_id=project.target_platform,
            novel_id=project.genre,
            language=project.language,
        )
        target = min(
            round((style.platform.chapter_word_min + style.platform.chapter_word_max) / 2),
            style.platform.chapter_word_max - 150,
        )
        base, remainder = divmod(target, len(scenes))
        scenes = [
            scene.model_copy(update={
                "target_word_count": base + (1 if index < remainder else 0),
                "target_word_min": max(1, base + (1 if index < remainder else 0) - 80),
                "target_word_max": base + (1 if index < remainder else 0) + 80,
            })
            for index, scene in enumerate(scenes)
        ]
        plan = plan.model_copy(update={
            "target_word_count": target,
            "target_word_min": style.platform.chapter_word_min,
            "target_word_max": style.platform.chapter_word_max,
        })
    return {"chapter": chapter, "plan": plan, "scenes": scenes}


@router.post("/projects/{project_id}/chapters/{number}/plan/submit")
async def submit_chapter_plan(
    project_id: UUID,
    number: int,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> ChapterPlan:
    chapter = await engine.chapters.get_by_number(project_id, number)
    plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
    if plan is None:
        raise InvalidStateError("chapter plan not found")
    return await engine.chapter_plans.submit_for_review(plan.id)


@router.post("/projects/{project_id}/chapters/{number}/plan/approve")
async def approve_chapter_plan(
    project_id: UUID,
    number: int,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    actor: Annotated[Actor, Depends(get_actor)],
) -> ChapterPlan:
    chapter = await engine.chapters.get_by_number(project_id, number)
    plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
    if plan is None:
        raise InvalidStateError("chapter plan not found")
    return await engine.chapter_plans.approve(
        plan.id,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )


@router.patch("/projects/{project_id}/chapters/{number}")
async def patch_chapter(
    project_id: UUID,
    number: int,
    body: ChapterPatch,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    actor: Annotated[Actor, Depends(get_actor)],
):
    chapter = await engine.chapters.get_by_number(project_id, number)
    if body.title is not None or body.story_arc_id is not None:
        chapter = await engine.chapters.update(
            chapter.model_copy(
                update={
                    "title": body.title or chapter.title,
                    "story_arc_id": body.story_arc_id if body.story_arc_id is not None else chapter.story_arc_id,
                }
            )
        )
    if body.content is not None:
        await engine.revisions.save_snapshot(
            chapter.id,
            body.content,
            created_by=actor.id,
            change_summary="human edit",
        )
        chapter = await engine.chapters.get_by_number(project_id, number)
        metadata = dict(chapter.extra_metadata or {})
        repetition_check = scan_chapter_repetition(
            chapter_number=number,
            content=chapter.content,
            chapters=await engine.chapters.list(project_id),
        )
        plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
        scenes = await engine.scene_plans.list(plan.id) if plan else []
        relevance_check = scan_chapter_relevance(content=chapter.content, plan=plan, scenes=scenes) if plan else None
        metadata["audit"] = {
            "status": "failed" if repetition_check.blocked or (relevance_check and relevance_check.blocked) else "pending",
            "repetition_check": repetition_check.model_dump(),
            "relevance_check": relevance_check.model_dump() if relevance_check else {"status": "missing_plan", "blocked": True},
        }
        chapter = await engine.chapters.update(chapter.model_copy(update={"extra_metadata": metadata}))
        await save_project_snapshot(engine, project_id)
    elif body.audit is not None:
        chapter = await engine.chapters.update(
            chapter.model_copy(
                update={
                    "extra_metadata": {
                        **(chapter.extra_metadata or {}),
                        "audit": body.audit,
                    }
                }
            )
        )
    return chapter


@router.post("/projects/{project_id}/chapters/{number}/review")
async def review_chapter(
    project_id: UUID,
    number: int,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    review_workflow: Annotated[AgentWorkflow | None, Depends(get_review_workflow)],
):
    if review_workflow is None:
        raise InvalidStateError("请先配置与生成模型不同的独立审查模型")
    context = await _writer_context(engine, project_id, number)
    chapter = await engine.chapters.get_by_number(project_id, number)
    project = await engine.get_project(project_id)
    if not chapter.content.strip():
        raise InvalidStateError("cannot review an empty chapter")
    repetition_check = scan_chapter_repetition(
        chapter_number=number,
        content=chapter.content,
        chapters=await engine.chapters.list(project_id),
    )
    plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
    scenes = await engine.scene_plans.list(plan.id) if plan else []
    relevance_check = scan_chapter_relevance(content=chapter.content, plan=plan, scenes=scenes) if plan else None
    if repetition_check.blocked or (relevance_check and relevance_check.blocked) or plan is None:
        metadata = dict(chapter.extra_metadata or {})
        metadata["audit"] = {
            **(metadata.get("audit") or {}),
            "status": "failed",
            "repetition_check": repetition_check.model_dump(),
            "relevance_check": relevance_check.model_dump() if relevance_check else {"status": "missing_plan", "blocked": True},
        }
        blocked = await engine.chapters.update(chapter.model_copy(update={"extra_metadata": metadata}))
        return {
            "chapter": blocked,
            "reviewed": False,
            "blocked_by_repetition": repetition_check.blocked,
            "blocked_by_relevance": bool(plan is None or (relevance_check and relevance_check.blocked)),
            "repetition_check": repetition_check,
            "relevance_check": relevance_check,
            "review_status": "failed",
        }
    result = await workflow.editor.run(EditorInput(context=context, prose=chapter.content))
    commercial = None
    if review_workflow is not None:
        commercial = (
            await review_workflow.review_commercial(
                CommercialReviewInput(context=context, prose=chapter.content)
            )
        ).output
    continuity_result = await workflow.continuity.run(
        ContinuityInput(context=context, prose=chapter.content)
    )
    alignment = scan_context_alignment(prose=chapter.content, context=context)
    continuity = ContinuityOutput(
        overall=continuity_result.output.overall,
        findings=[
            *continuity_result.output.findings,
            *scan_continuity_signals(
                prose=chapter.content,
                world_rules=list(context.world_rules),
                signals=resolve_style_bundle(
                    platform_id=project.target_platform,
                    novel_id=project.genre,
                    language=project.language,
                ).signals(),
            ),
            *alignment,
            *scan_commercial_quality(prose=chapter.content, context=context),
        ],
    )
    secondary = None
    if review_workflow is not None:
        secondary = (
            await review_workflow.continuity.run(
                ContinuityInput(context=context, prose=chapter.content)
            )
        ).output
        continuity = ContinuityOutput(
            overall=continuity.overall,
            findings=[*continuity.findings, *secondary.findings],
        )
    editor_blocked = result.output.needs_human_review or any(
        getattr(result.output, name).score < 6
        for name in (
            "pacing", "dialogue", "emotion", "character_voice", "show_dont_tell",
            "repetition", "grammar", "hook_strength", "romantic_tension", "plot_progress",
        )
    )
    commercial_blocked = review_workflow is not None and (
        commercial is None
        or (
            commercial.needs_human_review
            or commercial.reader_pressure_score < 6
            or commercial.reader_promise_score < 6
            or commercial.rhythm_score < 6
            or commercial.ai_style_risk_score < 5
        )
    )
    if continuity.overall is ContinuityVerdict.ERROR or editor_blocked or commercial_blocked:
        session = getattr(engine.uow, "session", None)
        if isinstance(session, AsyncSession):
            for finding in continuity.findings:
                session.add(
                    ContinuityIssue(
                        project_id=project_id,
                        chapter_id=chapter.id,
                        severity=_severity(finding.severity).value,
                        description=f"{finding.problem} | {finding.evidence}",
                        extra_metadata={"recommendation": finding.recommendation, "category": finding.category},
                    )
                )
            await session.commit()
        metadata = dict(chapter.extra_metadata or {})
        metadata["audit"] = {
            **(metadata.get("audit") or {}),
            "status": "failed",
            "independent_review": getattr(review_workflow, "provider_identity", None),
            "independent_commercial": commercial.model_dump() if commercial else None,
        }
        await engine.chapters.update(chapter.model_copy(update={"extra_metadata": metadata}))
        return {
            "chapter": chapter,
            "editor": result.output,
            "commercial_review": commercial,
            "continuity": continuity,
            "secondary_continuity": secondary,
            "repetition_check": repetition_check,
            "relevance_check": relevance_check,
            "reviewed": False,
            "blocked_by_continuity": continuity.overall is ContinuityVerdict.ERROR,
            "blocked_by_editor": editor_blocked,
            "blocked_by_commercial": commercial_blocked,
        }
    metadata = dict(chapter.extra_metadata or {})
    metadata["audit"] = {
        **(metadata.get("audit") or {}),
        "status": "passed",
        "independent_review": getattr(review_workflow, "provider_identity", None),
        "independent_commercial": commercial.model_dump() if commercial else None,
    }
    await engine.chapters.update(chapter.model_copy(update={"extra_metadata": metadata}))
    # Persist audit metadata before changing the lifecycle state. The chapter
    # service intentionally preserves the current status during metadata
    # updates, so updating metadata after mark_reviewed would silently revert
    # the row to its previous draft status in some repositories.
    reviewed = await engine.chapters.mark_reviewed(project_id, number)
    # Re-apply the reviewed state together with the audit metadata. This is
    # intentionally explicit at the API boundary so SQLAlchemy and in-memory
    # repositories cannot return a stale draft snapshot.
    reviewed = await engine.chapters.update(
        reviewed.model_copy(update={"status": ChapterStatus.REVIEWED, "extra_metadata": metadata})
    )
    # Reload after the state transition so the response reflects the durable
    # row, including repositories that expire ORM state on commit.
    reviewed = await engine.chapters.get_by_number(project_id, number)
    if reviewed.status is not ChapterStatus.REVIEWED:
        raise InvalidStateError("chapter review state was not persisted")
    return {
        "chapter": reviewed,
        "editor": result.output,
        "commercial_review": commercial,
        "continuity": continuity,
        "secondary_continuity": secondary,
        "repetition_check": repetition_check,
        "relevance_check": relevance_check,
        "reviewed": True,
        "review_status": "passed",
    }


@router.post("/projects/{project_id}/chapters/{number}/continuity")
async def continuity_chapter(
    project_id: UUID,
    number: int,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    review_workflow: Annotated[AgentWorkflow | None, Depends(get_review_workflow)],
):
    if review_workflow is None:
        raise InvalidStateError("请先配置与生成模型不同的独立审查模型")
    context = await _writer_context(engine, project_id, number)
    chapter = await engine.chapters.get_by_number(project_id, number)
    if not chapter.content.strip():
        raise InvalidStateError("cannot check continuity on an empty chapter")
    repetition_check = scan_chapter_repetition(
        chapter_number=number,
        content=chapter.content,
        chapters=await engine.chapters.list(project_id),
    )
    plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
    scenes = await engine.scene_plans.list(plan.id) if plan else []
    relevance_check = scan_chapter_relevance(content=chapter.content, plan=plan, scenes=scenes) if plan else None
    project = await engine.get_project(project_id)
    result = await workflow.continuity.run(ContinuityInput(context=context, prose=chapter.content))
    alignment = scan_context_alignment(prose=chapter.content, context=context)
    style = resolve_style_bundle(
        platform_id=project.target_platform,
        novel_id=project.genre,
        language=project.language,
    )
    local_signals = scan_continuity_signals(
        prose=chapter.content,
        world_rules=list(context.world_rules or []),
        signals=style.signals(),
    )
    continuity = ContinuityOutput(
        overall=result.output.overall,
        findings=[
            *result.output.findings,
            *alignment,
            *local_signals,
            *scan_commercial_quality(prose=chapter.content, context=context),
        ],
    )
    secondary = None
    if review_workflow is not None:
        secondary = (
            await review_workflow.continuity.run(
                ContinuityInput(context=context, prose=chapter.content)
            )
        ).output
        continuity = ContinuityOutput(
            overall=continuity.overall,
            findings=[*continuity.findings, *secondary.findings],
        )
    session = getattr(engine.uow, "session", None)
    if isinstance(session, AsyncSession):
        for finding in continuity.findings:
            session.add(
                ContinuityIssue(
                    project_id=project_id,
                    chapter_id=chapter.id,
                    severity=_severity(finding.severity).value,
                    description=f"{finding.problem} | {finding.evidence}",
                    extra_metadata={"recommendation": finding.recommendation, "category": finding.category},
                )
            )
        await session.commit()
    metadata = dict(chapter.extra_metadata or {})
    metadata["audit"] = {
        **(metadata.get("audit") or {}),
        "status": "failed" if continuity.overall is ContinuityVerdict.ERROR or repetition_check.blocked or plan is None or (relevance_check and relevance_check.blocked) else "completed",
        "repetition_check": repetition_check.model_dump(),
        "relevance_check": relevance_check.model_dump() if relevance_check else {"status": "missing_plan", "blocked": True},
    }
    await engine.chapters.update(chapter.model_copy(update={"extra_metadata": metadata}))
    return {
        "chapter": chapter,
        "continuity": continuity,
        "secondary_continuity": secondary,
        "repetition_check": repetition_check,
        "relevance_check": relevance_check,
        "review_status": "failed" if continuity.overall is ContinuityVerdict.ERROR or repetition_check.blocked or plan is None or (relevance_check and relevance_check.blocked) else "completed",
    }


@router.post("/projects/{project_id}/chapters/{number}/approve")
async def approve_chapter(
    project_id: UUID,
    number: int,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    review_workflow: Annotated[AgentWorkflow | None, Depends(get_review_workflow)],
    actor: Annotated[Actor, Depends(get_actor)],
):
    if review_workflow is None:
        raise InvalidStateError("未完成独立审查，不能批准章节")
    pipeline = await _pipeline(engine, workflow, project_id)
    result = await pipeline.commit_approved_chapter(
        project_id,
        number,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )
    session = getattr(engine.uow, "session", None)
    if isinstance(session, AsyncSession):
        await persist_commit(session, project_id, result.chapter.id, pipeline, result)
    await save_project_snapshot(engine, project_id)
    return result.chapter


async def _pipeline(
    engine: NovelEngine,
    workflow: AgentWorkflow,
    project_id: UUID,
    *,
    review_workflow: AgentWorkflow | None = None,
) -> ChapterGenerationPipeline:
    memory = MemoryService()
    history = None
    session = getattr(engine.uow, "session", None)
    if isinstance(session, AsyncSession):
        history = await hydrate_pipeline_memory(session, project_id, memory)
    return ChapterGenerationPipeline(
        engine, workflow, memory, style_history=history, review_workflow=review_workflow
    )


async def _writer_context(engine: NovelEngine, project_id: UUID, number: int):
    project = await engine.get_project(project_id)
    bible = await engine.story_bibles.get(project_id)
    if bible is None:
        raise InvalidStateError("story bible is required before generating a chapter")
    world = await engine.world_bibles.get(project_id)
    characters = await engine.characters.list(project_id)
    chapter = await engine.chapters.get_by_number(project_id, number)
    plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
    if plan is None:
        raise InvalidStateError("create a chapter plan before generating")
    scenes = await engine.scene_plans.list(plan.id)
    if not scenes:
        raise InvalidStateError("add at least one scene plan before generating")
    hooks = await engine.hooks.list(project_id, open_only=True)
    return build_writer_context(
        bible=bible,
        world=world,
        characters=characters,
        plan=plan,
        scenes=scenes,
        open_hooks=[item.description for item in hooks],
        language=project.language,
        creative_profile=(project.extra_metadata or {}).get("creative_profile", {}),
    )


def _severity(verdict: ContinuityVerdict) -> ContinuitySeverity:
    if verdict is ContinuityVerdict.ERROR:
        return ContinuitySeverity.HIGH
    if verdict is ContinuityVerdict.WARNING:
        return ContinuitySeverity.MEDIUM
    return ContinuitySeverity.LOW
