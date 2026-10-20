from __future__ import annotations

import hashlib
import json
from difflib import SequenceMatcher
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.memory_bridge import (
    _fact_dedupe_key,
    hydrate_pipeline_memory,
    hydrate_draft_expression_history,
    persist_commit,
    persist_style_ledger,
)
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
from app.api.schemas import AutoNextChapterBody, ChapterPatch, ChapterPlanCreate, ChapterPlanSuggest, ConfirmBody, GenerateBody, ProposeEditBody
from app.services.book_snapshot import save_project_snapshot
from app.services.creative_quality import rank_creative_candidates
from app.services.prompt_optimization import chapter_optimization_signals
from app.services.platform_publishers import get_platform_publisher
from app.core.config import get_settings
from app.db.models.chapter import ChapterSummary
from app.db.models.automation import AutomationTask, PublishTask
from app.db.models.memory import StoryMemory, TimelineEvent
from app.db.models.continuity import ContinuityIssue
from novel_engine.agents.contracts import (
    ChapterPlannerInput,
    ChapterSummaryInput,
    CommercialReviewInput,
    ContinuityOutput,
    ContinuityInput,
    EditorInput,
    OutlineOutput,
    ReviseInput,
    MemoryAgentInput,
    WriterInput,
)
from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.memory.embeddings import ProviderEmbedder
from novel_engine.memory.service import MemoryService
from novel_engine.models.entities import ChapterPlan, Hook, ScenePlan
from novel_engine.creative.contract import contract_for_project
from novel_engine.models.enums import ApprovalStatus, ChapterStatus, ContinuitySeverity, ContinuityVerdict, ProjectStatus
from novel_engine.models.enums import EpistemicStatus, Importance, MemoryLayer, MemoryType
from novel_engine.presets.loader import resolve_style_bundle
from novel_engine.style.quality_gate import evaluate_chapter_quality
from novel_engine.providers.base import LLMProvider
from novel_engine.providers.types import ChatMessage
from novel_engine.services.engine import NovelEngine
from novel_engine.workflows.agent_workflow import AgentWorkflow
from novel_engine.workflows.chapter_pipeline import ChapterGenerationPipeline, is_local_revision
from novel_engine.workflows.context import character_to_agent, plan_to_agent, plot_to_outline, story_bible_to_architect
from novel_engine.style.memory_continuity import scan_scene_handoffs
from novel_engine.style.longitudinal_continuity import scan_longitudinal_continuity
from novel_engine.style.story_state_continuity import scan_story_state_continuity
from novel_engine.style.plot_thread_lifecycle import scan_plot_thread_lifecycle
from novel_engine.style.canon import scan_context_alignment
from novel_engine.style.commercial import scan_commercial_quality
from novel_engine.style.chapter_repetition import scan_book_repetition, scan_chapter_repetition
from novel_engine.style.chapter_relevance import scan_chapter_relevance
from novel_engine.style.completeness import escalate_verdict, scan_prose_completeness
from novel_engine.style.word_count import count_text_units
from novel_engine.style.signals import scan_continuity_signals
from novel_engine.style.anti_repetition import StyleHistory
from novel_engine.agents.contracts import ChapterPlannerInput, ContinuityInput, EditorInput, OutlineOutput, ReviseInput
from novel_engine.workflows.context import character_to_agent, plot_to_outline, story_bible_to_architect

router = APIRouter(tags=["chapters"])


def _title_key(value: str) -> str:
    return "".join(value.split()).casefold()


async def _ensure_unique_chapter_title(
    project_id: UUID,
    chapter_number: int,
    title: str,
    engine: NovelEngine,
) -> str:
    chapters = await engine.chapters.list(project_id)
    existing_keys = {
        _title_key(item.title)
        for item in chapters
        if item.chapter_number != chapter_number and _title_key(item.title)
    }
    if _title_key(title) not in existing_keys:
        return title

    base = title.strip()
    candidate = f"{base}（第{chapter_number}章）"
    suffix = 2
    while _title_key(candidate) in existing_keys:
        candidate = f"{base}（第{chapter_number}章·{suffix}）"
        suffix += 1
    return candidate


async def _sync_project_writing_status(engine: NovelEngine, project_id: UUID) -> None:
    """Keep the project status aligned once it contains actual prose."""
    project = await engine.get_project(project_id)
    if project.status in {ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED, ProjectStatus.WRITING, ProjectStatus.REVISING}:
        return
    await engine.update_project(project.model_copy(update={"status": ProjectStatus.WRITING}))


def _content_fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _chapter_length_check(project, prose: str) -> dict:
    style = resolve_style_bundle(
        platform_id=project.target_platform,
        novel_id=project.genre,
        language=project.language,
    )
    count = count_text_units(prose)
    minimum = style.platform.chapter_word_min
    maximum = style.platform.chapter_word_max
    return {
        "count": count,
        "minimum": minimum,
        "maximum": maximum,
        "ok": minimum <= count <= maximum,
    }


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
    candidates: list[str] = Field(default_factory=list)


@router.get("/projects/{project_id}/chapters")
async def list_chapters(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    return await engine.chapters.list(project_id)


@router.get("/projects/{project_id}/chapters/{number}/context-pack")
async def chapter_context_pack(
    project_id: UUID,
    number: int,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    """Return the read-only memory package that would be supplied to the writer."""
    memory = MemoryService()
    session = getattr(engine.uow, "session", None)
    history = await hydrate_pipeline_memory(session, project_id, memory) if isinstance(session, AsyncSession) else None
    pipeline = ChapterGenerationPipeline(engine, None, memory, style_history=history)
    loaded = await pipeline.load(project_id, number)
    writer_context = loaded.writer_context
    return {
        "chapter_number": number,
        "chapter_title": loaded.plan.chapter_title,
        "story_arc": {
            "title": loaded.arc.title,
            "start_chapter_number": loaded.arc.start_chapter_number,
            "end_chapter_number": loaded.arc.end_chapter_number,
            "summary": loaded.arc.summary,
        } if loaded.arc else None,
        "next_plot_beat": (
            getattr(loaded.arc, "summary", None)
            or getattr(loaded.plot, "summary", None)
            or loaded.bible.premise
        ),
        "context": writer_context.model_dump(mode="json"),
        "memory_package": loaded.package.model_dump(mode="json"),
        "visible_text": loaded.package.visible_text(),
    }


@router.post("/projects/{project_id}/memory/backfill")
async def backfill_project_memory(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
) -> dict:
    """Extract durable summaries and knowledge boundaries for older approved chapters.

    The operation is idempotent: chapters that already have a chapter-memory row
    are reported as existing and are not duplicated.
    """
    await engine.get_project(project_id)
    session = getattr(engine.uow, "session", None)
    if not isinstance(session, AsyncSession):
        raise InvalidStateError("memory backfill requires the database session")
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"story-memory-backfill:{project_id}"},
    )
    chapters = sorted(await engine.chapters.list(project_id), key=lambda item: item.chapter_number)
    characters = await engine.characters.list(project_id)
    allowed_names = {item.name for item in characters}
    existing_rows = (
        await session.scalars(select(StoryMemory).where(StoryMemory.project_id == project_id))
    ).all()
    existing_chapters = {
        row.source_chapter_id
        for row in existing_rows
        if (row.extra_metadata or {}).get("kind") == "chapter_memory"
    }
    processed: list[int] = []
    existing: list[int] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    for chapter in chapters:
        if chapter.status not in {ChapterStatus.APPROVED, ChapterStatus.PUBLISHED}:
            skipped.append({"chapter_number": chapter.chapter_number, "reason": "not_approved"})
            continue
        if chapter.id in existing_chapters:
            existing.append(chapter.chapter_number)
            continue
        plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
        if plan is None or not chapter.content.strip():
            skipped.append({"chapter_number": chapter.chapter_number, "reason": "missing_plan_or_content"})
            continue
        scenes = await engine.scene_plans.list(plan.id)
        savepoint = await session.begin_nested()
        try:
            plan_input = plan_to_agent(plan, scenes)
            summary = (
                await workflow.chapter_summary.run(
                    ChapterSummaryInput(
                        chapter_number=chapter.chapter_number,
                        chapter_plan=plan_input,
                        prose=chapter.content,
                    )
                )
            ).output
            memory_result = (
                await workflow.memory.run(
                    MemoryAgentInput(
                        chapter_number=chapter.chapter_number,
                        prose=chapter.content,
                        chapter_plan=plan_input,
                    )
                )
            ).output
            handoffs = list(summary.scene_handoffs)
            findings = scan_scene_handoffs(
                prose=chapter.content,
                handoffs=handoffs,
                planned_scene_numbers={item.scene_number for item in scenes},
                planned_scene_locations={item.scene_number: item.location for item in scenes},
                planned_scene_characters={item.scene_number: set(item.characters) for item in scenes},
                allowed_characters=allowed_names | set(plan.characters),
            )
            stored_summary = await session.scalar(
                select(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id)
            )
            summary_values = dict(
                summary=summary.summary,
                key_events=list(summary.key_events),
                new_facts=list(summary.new_facts),
                character_changes=list(summary.character_changes),
                new_secrets=list(summary.new_secrets),
                resolved_secrets=list(summary.resolved_secrets),
                unresolved_hooks=list(summary.unresolved_hooks),
                location=summary.location or plan.location,
            )
            if stored_summary is None:
                session.add(
                    ChapterSummary(
                    chapter_id=chapter.id,
                        **summary_values,
                    )
                )
            else:
                for key, value in summary_values.items():
                    setattr(stored_summary, key, value)
            session.add(
                StoryMemory(
                    project_id=project_id,
                    memory_type=MemoryType.PLOT.value,
                    layer=MemoryLayer.CHAPTER.value,
                    epistemic_status=EpistemicStatus.CONFIRMED_FACT.value,
                    importance=Importance.HIGH.value,
                     source_chapter_id=chapter.id,
                     dedupe_key=f"chapter_memory:{chapter.id}",
                     chapter_number=chapter.chapter_number,
                    location=summary.location or plan.location,
                    content=summary.summary,
                    known_by=list(plan.characters),
                    tags=["chapter", "backfilled"],
                    extra_metadata={
                        "kind": "chapter_memory",
                        "title": summary.title or plan.chapter_title,
                        "key_events": list(summary.key_events),
                        "new_facts": list(summary.new_facts),
                        "character_changes": list(summary.character_changes),
                        "unresolved_hooks": list(summary.unresolved_hooks),
                        "characters": list(plan.characters),
                        "scene_handoffs": [item.model_dump() for item in handoffs],
                        "memory_validation": {
                            "overall": "error" if any(item.severity is ContinuityVerdict.ERROR for item in findings) else "pass",
                            "findings": [item.model_dump(mode="json") for item in findings],
                        },
                    },
                )
            )
            for item in memory_result.memories:
                session.add(
                    StoryMemory(
                        project_id=project_id,
                        memory_type=item.memory_type.value,
                        layer=(MemoryLayer.CHARACTER if item.character_name else MemoryLayer.CHAPTER).value,
                        epistemic_status=EpistemicStatus.TENTATIVE_FACT.value,
                        importance=item.importance.value,
                         source_chapter_id=chapter.id,
                         dedupe_key=_fact_dedupe_key("fact", chapter.id, item.content),
                         chapter_number=chapter.chapter_number,
                        content=item.content,
                        known_by=list(item.known_by) or (list(plan.characters) if not item.character_name else []),
                        tags=["backfilled", "fact"],
                        extra_metadata={
                            "kind": "fact",
                            "character_name": item.character_name,
                            "source_excerpt": item.source_excerpt,
                        },
                        unknown_to=list(item.unknown_to),
                    )
                )
            for handoff in handoffs:
                facts: dict[str, dict[str, list[str]]] = {}
                for name, items in handoff.who_knows.items():
                    for fact in items:
                        facts.setdefault(fact, {}).setdefault("known_by", []).append(name)
                for name, items in handoff.unknown_to.items():
                    for fact in items:
                        facts.setdefault(fact, {}).setdefault("unknown_to", []).append(name)
                for fact, visibility in facts.items():
                    session.add(
                        StoryMemory(
                            project_id=project_id,
                            memory_type=MemoryType.FACT.value,
                            layer=MemoryLayer.CHARACTER.value,
                            epistemic_status=EpistemicStatus.TENTATIVE_FACT.value,
                            importance=Importance.MEDIUM.value,
                             source_chapter_id=chapter.id,
                             dedupe_key=_fact_dedupe_key("knowledge_boundary", chapter.id, fact),
                             chapter_number=chapter.chapter_number,
                            content=fact,
                            known_by=visibility.get("known_by", []),
                            unknown_to=visibility.get("unknown_to", []),
                            tags=["backfilled", "scene_handoff", f"scene:{handoff.scene_number}"],
                            extra_metadata={"kind": "knowledge_boundary", "source_excerpt": handoff.source_excerpt},
                        )
                    )
            processed.append(chapter.chapter_number)
            await savepoint.commit()
        except Exception as exc:
            errors.append({"chapter_number": chapter.chapter_number, "reason": str(exc)})
            await savepoint.rollback()
    await session.commit()
    return {
        "processed": processed,
        "already_present": existing,
        "skipped": skipped,
        "errors": errors,
        "complete": not errors and not skipped,
    }


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
    plans_by_chapter: dict[int, object] = {}
    for chapter in chapters:
        plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
        if plan is None:
            missing_plans.append(chapter.chapter_number)
            continue
        plans_by_chapter[chapter.chapter_number] = plan
        scenes = await engine.scene_plans.list(plan.id)
        relevance = scan_chapter_relevance(content=chapter.content, plan=plan, scenes=scenes)
        if relevance.blocked:
            relevance_findings.append({
                "chapter_number": chapter.chapter_number,
                **relevance.model_dump(),
            })
        completeness = scan_prose_completeness(chapter.content)
        if completeness:
            relevance_findings.append({
                "chapter_number": chapter.chapter_number,
                "status": "blocked",
                "blocked": True,
                "completeness_findings": [item.model_dump(mode="json") for item in completeness],
            })
    chapter_memories: dict[int, dict] = {}
    memory_rows = []
    session = getattr(engine.uow, "session", None)
    if isinstance(session, AsyncSession):
        memory_rows = (
            await session.scalars(select(StoryMemory).where(StoryMemory.project_id == project_id))
        ).all()
        for row in memory_rows:
            metadata = row.extra_metadata or {}
            if metadata.get("kind") == "chapter_memory" and row.chapter_number is not None:
                chapter_memories[row.chapter_number] = {
                    "summary": row.content,
                    "scene_handoffs": list(metadata.get("scene_handoffs") or []),
                }
    longitudinal_findings = scan_longitudinal_continuity(
        chapters=chapters,
        chapter_memories=chapter_memories,
        target_chapter_count=target,
    )
    approved_chapter_numbers = {
        item.chapter_number
        for item in chapters
        if item.status.value in {"approved", "published"}
    }
    missing_memory = sorted(approved_chapter_numbers - set(chapter_memories))
    timeline_rows = []
    if isinstance(session, AsyncSession):
        timeline_rows = (
            await session.scalars(
                select(TimelineEvent).where(TimelineEvent.project_id == project_id)
            )
        ).all()
    story_state_findings = scan_story_state_continuity(
        chapters=chapters,
        plans=plans_by_chapter,
        arcs=arcs,
        plot_beats=active_plot.beats if active_plot else [],
        timeline_events=timeline_rows,
        memory_rows=memory_rows,
    )
    chapter_id_numbers = {item.id: item.chapter_number for item in chapters}
    hooks = await engine.hooks.list(project_id)
    foreshadowings = await engine.foreshadowings.list(project_id)
    latest_approved = max(
        (item.chapter_number for item in chapters if item.status.value in {"approved", "published"}),
        default=0,
    )
    plot_thread_findings = scan_plot_thread_lifecycle(
        hooks=hooks,
        foreshadowings=foreshadowings,
        chapter_numbers=chapter_id_numbers,
        latest_approved_chapter=latest_approved,
    )
    length_findings = [
        {"chapter_number": item.chapter_number, **_chapter_length_check(project, item.content)}
        for item in chapters
        if item.content.strip() and not _chapter_length_check(project, item.content)["ok"]
    ]
    blocked = bool(
        missing
        or overflow
        or empty
        or unfinished
        or repetition_findings
        or relevance_findings
        or missing_plans
        or missing_architecture
        or any(item.severity is ContinuityVerdict.ERROR for item in longitudinal_findings)
        or any(item.severity is ContinuityVerdict.ERROR for item in story_state_findings)
        or any(item.severity is ContinuityVerdict.ERROR for item in plot_thread_findings)
        or length_findings
        or missing_memory
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
        "longitudinal_findings": [item.model_dump(mode="json") for item in longitudinal_findings],
        "story_state_findings": [item.model_dump(mode="json") for item in story_state_findings],
        "plot_thread_findings": [item.model_dump(mode="json") for item in plot_thread_findings],
        "length_findings": length_findings,
        "missing_memory": missing_memory,
        "plot_thread_coverage": {
            "open_hooks": sum(item.status.value not in {"resolved", "dropped"} for item in hooks),
            "open_foreshadowings": sum(item.status.value not in {"paid_off", "missed", "dropped"} for item in foreshadowings),
        },
        "memory_coverage": {
            "chapters_with_memory": len(chapter_memories),
            "approved_chapters": len(approved_chapter_numbers),
            "missing_chapters": missing_memory,
        },
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
                    "You are a fiction editor naming a chapter. Create 5 distinct concise, memorable "
                    "chapter title in the same language and style as the novel. Use the supplied "
                    f"story and previous chapter context. The novel output language is {project.language}; "
                    "write every title entirely in that language. Vary conflict, mystery, reversal, "
                    "emotion, and a concrete event. Do not use generic labels or reveal the whole ending. "
                    "Return JSON with title and candidates only."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    f"Novel title: {project.title}\nGenre: {project.genre}\n"
                    f"Next chapter number: {next_number}\n{story_context}\n"
                    f"Plot outline: {plot_context}\n{previous_context}\n"
                    "Generate apt titles for the next chapter. They should not simply be 'Chapter N' "
                    "and must be grounded in the supplied chapter context."
                ),
            ),
        ],
        ChapterTitleSuggestion,
        temperature=0.8,
    )
    ranked = rank_creative_candidates(
        [result.title, *result.candidates],
        existing=[item.title for item in chapters],
    )
    if not ranked:
        fallback = result.title.strip().strip("\"'“”‘’")
        if not fallback:
            raise InvalidStateError("the model returned an empty chapter title")
        fallback = await _ensure_unique_chapter_title(
            project_id,
            next_number,
            fallback,
            engine,
        )
        ranked = [{"text": fallback, "score": 0, "reasons": ["已自动追加章节号避免重复"]}]
    title = ranked[0]["text"]
    return {"title": title, "candidates": ranked}


@router.post("/projects/{project_id}/chapters/plan", status_code=status.HTTP_201_CREATED)
async def create_chapter_plan(
    project_id: UUID,
    body: ChapterPlanCreate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    if not body.scenes:
        raise InvalidStateError("chapter plan must contain at least one scene")
    unique_title = await _ensure_unique_chapter_title(
        project_id,
        body.chapter_number,
        body.chapter_title,
        engine,
    )
    plan = await engine.chapter_plans.create(
        ChapterPlan(
            project_id=project_id,
            chapter_number=body.chapter_number,
            chapter_title=unique_title,
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
        ),
        auto_approve=False,
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
    creative_contract = contract_for_project(project)
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
            creative_contract=creative_contract,
        )
    )
    if not proposal.output.scenes or not proposal.output.characters:
        raise InvalidStateError("AI 章节计划必须包含角色和至少一个场景，请重试或完善角色设定")
    unique_title = await _ensure_unique_chapter_title(
        project_id,
        body.chapter_number,
        proposal.output.chapter_title,
        engine,
    )
    proposal_output = proposal.output.model_copy(update={"chapter_title": unique_title})
    return _apply_chapter_budgets(
        proposal_output,
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
        project = await engine.get_project(project_id)
        length_check = _chapter_length_check(project, chapter_row.content)
        commercial = result.secondary_commercial
        quality_gate = evaluate_chapter_quality(
            continuity=result.continuity,
            editor=result.bundle.editor.output,
            length_ok=result.length_ok,
            repetition_check=result.repetition_check,
            relevance_check=result.relevance_check,
            sequence_review=result.sequence_review,
            commercial=commercial,
            require_independent_review=True,
        )
        optimization_signals = chapter_optimization_signals(
            chapter_number=number,
            audit={
                "length_check": length_check,
                "repetition_check": result.repetition_check,
                "relevance_check": result.relevance_check,
            },
            editor=result.bundle.editor.output,
            commercial=commercial.model_dump(mode="json") if commercial else None,
        )
        metadata["audit"] = {
            "status": (
                "blocked" if not quality_gate.passed else "passed"
            ),
            "versions": [item.model_dump() for item in result.versions],
            "repetition_check": result.repetition_check,
            "relevance_check": result.relevance_check,
            "independent_review": getattr(review_workflow, "provider_identity", None),
            "independent_commercial": commercial.model_dump() if commercial else None,
            "content_fingerprint": _content_fingerprint(chapter_row.content),
            "length_check": length_check,
            "sequence_review": [item.model_dump(mode="json") for item in result.sequence_review],
            "quality_gate": {
                "status": quality_gate.status,
                "blocking_reasons": list(quality_gate.blocking_reasons),
                "warnings": list(quality_gate.warnings),
            },
            "optimization_signals": optimization_signals,
        }
        await engine.chapters.update(chapter_row.model_copy(update={"extra_metadata": metadata}))
        if review_workflow is not None or optimization_signals:
            quality_reviews = list((project.extra_metadata or {}).get("quality_reviews") or [])
            quality_reviews.append({
                "review_type": "chapter_independent",
                "chapter_number": number,
                "status": metadata["audit"]["status"],
                "independent_commercial": commercial.model_dump() if commercial else None,
                "independent_review": getattr(review_workflow, "provider_identity", None),
                "optimization_signals": optimization_signals,
            })
            await engine.update_project(project.model_copy(update={
                "extra_metadata": {**(project.extra_metadata or {}), "quality_reviews": quality_reviews[-50:]}
            }))
        if chapter_row.content.strip():
            await _sync_project_writing_status(engine, project_id)
        session = getattr(engine.uow, "session", None)
        if isinstance(session, AsyncSession):
            await persist_style_ledger(session, project_id, pipeline)
            await session.commit()
        await save_project_snapshot(engine, project_id)
    auto_approved = False
    quality_gate = evaluate_chapter_quality(
        continuity=result.continuity,
        editor=result.bundle.editor.output,
        length_ok=result.length_ok,
        repetition_check=result.repetition_check,
        relevance_check=result.relevance_check,
        sequence_review=result.sequence_review,
        commercial=result.secondary_commercial,
        require_independent_review=True,
    )
    if body.persist and quality_gate.passed and review_workflow is not None:
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
            try:
                await persist_commit(session, project_id, pipeline_result.chapter.id, pipeline, pipeline_result)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        chapter_row = await engine.chapters.get_by_number(project_id, number)
        if chapter_row.content.strip():
            await _sync_project_writing_status(engine, project_id)
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
            "passed" if quality_gate.passed else "blocked"
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
        "requires_human_approval": not auto_approved,
        "auto_approved": auto_approved,
        "advances_next_chapter": False,
    }


@router.post("/projects/{project_id}/chapters/auto-next")
async def auto_generate_next_chapter(
    project_id: UUID,
    body: AutoNextChapterBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    actor: Annotated[Actor, Depends(get_actor)],
    review_workflow: Annotated[AgentWorkflow | None, Depends(get_review_workflow)],
) -> dict:
    """Generate the next chapter through the existing audited pipeline.

    This is intentionally synchronous for the first automation milestone: the
    caller gets a complete result and can safely refresh without guessing
    whether a background task is still running.  The persisted audit metadata
    makes this endpoint safe to promote to a durable queue later.
    """
    chapters = await engine.chapters.list(project_id)
    next_number = body.target_chapter_number or (max((item.chapter_number for item in chapters), default=0) + 1)
    try:
        existing = await engine.chapters.get_by_number(project_id, next_number)
    except NotFoundError:
        # The next chapter is expected not to exist yet. The chapter-plan
        # service creates the empty chapter slot before generation.
        existing = None
    if existing is not None and existing.content.strip():
        raise InvalidStateError(f"第 {next_number} 章已有正文，不能重复自动生成")

    session = getattr(engine.uow, "session", None)
    automation_task = None
    if isinstance(session, AsyncSession):
        automation_task = AutomationTask(
            project_id=project_id,
            task_type="generate_next_chapter",
            status="running",
            chapter_number=next_number,
            max_attempts=body.max_attempts,
            payload={"human_notes": body.human_notes or ""},
            started_at=datetime.now(timezone.utc),
        )
        session.add(automation_task)
        await session.flush()

    suggestion = await suggest_chapter_plan(
        project_id,
        ChapterPlanSuggest(chapter_number=next_number),
        engine,
        workflow,
    )
    plan_body = ChapterPlanCreate.model_validate(suggestion.model_dump(mode="json"))
    created = await create_chapter_plan(project_id, plan_body, engine)
    plan = created["plan"]
    await engine.chapter_plans.submit_for_review(plan.id)
    plan = await engine.chapter_plans.approve(plan.id, confirmed_by=actor.id or "system-auto")

    attempts: list[dict] = []
    result: dict | None = None
    for attempt in range(1, body.max_attempts + 1):
        result = await generate_chapter(
            project_id,
            next_number,
            GenerateBody(
                human_notes=body.human_notes or "自动生成下一章，并按审核结果自动重试。",
                persist=True,
                overwrite_human=attempt > 1,
            ),
            engine,
            workflow,
            actor,
            review_workflow,
        )
        attempts.append({
            "attempt": attempt,
            "review_status": result["review_status"],
            "auto_approved": result["auto_approved"],
            "length_ok": result["length_ok"],
        })
        if result["review_status"] == "passed":
            break

    assert result is not None
    chapter = await engine.chapters.get_by_number(project_id, next_number)
    if automation_task is not None and isinstance(session, AsyncSession):
        automation_task.status = "completed" if result["review_status"] == "passed" else "needs_human_review"
        automation_task.attempt_count = len(attempts)
        automation_task.result = {"review_status": result["review_status"], "attempts": attempts}
        automation_task.completed_at = datetime.now(timezone.utc)
        await session.commit()
    draft_upload = None
    if result["review_status"] == "passed":
        try:
            draft_upload = await queue_chapter_draft_upload(project_id, next_number, {}, engine)
        except Exception as exc:
            draft_upload = {"status": "blocked", "error": str(exc)[:1000]}
    return {
        "chapter": chapter,
        "chapter_number": next_number,
        "plan": plan,
        "attempts": attempts,
        "completed": result["review_status"] == "passed",
        "requires_human_approval": result["requires_human_approval"],
        "review_status": result["review_status"],
        "next_action": "open_chapter" if result["review_status"] == "passed" else "human_review",
        "draft_upload": draft_upload,
    }


@router.post("/projects/{project_id}/chapters/{number}/publish/draft")
async def queue_chapter_draft_upload(
    project_id: UUID,
    number: int,
    body: dict,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    """Create per-platform upload records without pretending an upload happened.

    Platform credentials and official upload APIs are intentionally external to
    the writing pipeline.  Until an adapter is configured, rows remain
    ``not_configured`` and can be retried independently.
    """
    project = await engine.get_project(project_id)
    platform = (project.target_platform or "").strip().lower()
    if platform not in {"fanqie", "qidian", "qimao"}:
        raise InvalidStateError("当前作品的平台标记不支持自动上传")
    requested_platforms = list(dict.fromkeys(body.get("platforms") or [platform]))
    if requested_platforms != [platform]:
        raise InvalidStateError(
            f"作品平台标记为 {platform}，不能跨平台上传；本次只能上传到 {platform}"
        )
    chapter = await engine.chapters.get_by_number(project_id, number)
    if not chapter.content.strip():
        raise InvalidStateError("不能上传空章节")
    session = getattr(engine.uow, "session", None)
    if not isinstance(session, AsyncSession):
        raise InvalidStateError("发布队列需要数据库会话")
    rows = []
    settings = get_settings()
    platforms = [platform]
    for platform in platforms:
        row = await session.scalar(
            select(PublishTask).where(PublishTask.chapter_id == chapter.id, PublishTask.platform == platform)
        )
        if row is None:
            row = PublishTask(
                project_id=project_id,
                chapter_id=chapter.id,
                platform=platform,
                local_chapter_number=number,
                platform_book_id=project.platform_book_id,
                platform_chapter_number=number,
                platform_chapter_title=chapter.title,
                content_fingerprint=_content_fingerprint(chapter.content),
                status="pending",
                payload={"title": chapter.title, "content": chapter.content},
                error_message=None,
            )
            session.add(row)
            await session.flush()
        if row.local_chapter_number != number:
            row.status = "failed"
            row.error_message = "本地章节映射不一致，已阻止重复或错章上传"
        elif row.platform_book_id and project.platform_book_id and row.platform_book_id != project.platform_book_id:
            row.status = "failed"
            row.error_message = "平台书籍 ID 已变化，需重新确认绑定后再上传"
        elif not project.platform_book_id:
            row.status = "needs_book_binding"
            row.error_message = "请先绑定该作品在目标平台的书籍 ID"
        else:
            publisher = get_platform_publisher(platform, settings)
            if publisher is None:
                row.status = "not_configured"
                row.error_message = "尚未配置该平台的上传适配器或授权凭据"
            elif row.status not in {"awaiting_confirmation", "confirmed", "published"}:
                row.status = "uploading"
                row.attempts += 1
                try:
                    uploaded = await publisher.upload_draft({
                        **row.payload,
                        "platform_book_id": project.platform_book_id,
                        "chapter_number": number,
                    })
                    response_chapter_number = uploaded.response.get("chapter_number")
                    if response_chapter_number is not None and int(response_chapter_number) != number:
                        raise RuntimeError(
                            f"平台返回章节号 {response_chapter_number}，预期为 {number}，已阻止错章确认"
                        )
                    row.status = "awaiting_confirmation"
                    row.external_chapter_id = uploaded.external_id
                    row.platform_book_id = project.platform_book_id
                    row.platform_chapter_number = int(response_chapter_number or number)
                    row.platform_chapter_title = chapter.title
                    row.response = uploaded.response
                    row.error_message = None
                except Exception as exc:
                    row.status = "failed"
                    row.error_message = str(exc)[:1000]
        rows.append(row)
    await session.commit()
    statuses = {row.status for row in rows}
    if statuses and statuses.issubset({"awaiting_confirmation", "draft_uploaded", "confirmed", "published"}):
        next_action = "human_confirm_publish"
    elif "failed" in statuses:
        next_action = "retry_failed_platforms"
    else:
        next_action = "configure_platform_adapter"
    return {"chapter_number": number, "tasks": rows, "next_action": next_action}


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
            "content_fingerprint": _content_fingerprint(chapter.content),
        }
        chapter = await engine.chapters.update(chapter.model_copy(update={"extra_metadata": metadata}))
        if chapter.content.strip():
            await _sync_project_writing_status(engine, project_id)
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


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _clean_streamed_prose(value: str) -> str:
    text_value = value.strip()
    if text_value.startswith("```"):
        text_value = text_value.removeprefix("```").removeprefix("json").removesuffix("```").strip()
    if text_value.startswith("{"):
        try:
            parsed = json.loads(text_value)
            if isinstance(parsed, dict) and isinstance(parsed.get("prose"), str):
                return parsed["prose"].strip()
        except json.JSONDecodeError:
            pass
    return text_value


@router.post("/projects/{project_id}/chapters/{number}/generate/stream")
async def generate_chapter_stream(
    project_id: UUID,
    number: int,
    body: GenerateBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    actor: Annotated[Actor, Depends(get_actor)],
):
    async def events():
        try:
            yield _sse_event("stage", {"stage": "preparing", "message": "正在整理章节上下文"})
            context = await _writer_context(engine, project_id, number)
            yield _sse_event("stage", {"stage": "streaming", "message": "正在生成正文"})
            chunks: list[str] = []
            async for delta in workflow.writer.stream_prose(
                WriterInput(context=context, human_notes=body.human_notes)
            ):
                chunks.append(delta)
                yield _sse_event("delta", {"text": delta})
            prose = _clean_streamed_prose("".join(chunks))
            if not prose:
                raise InvalidStateError("AI 没有返回有效正文")
            project = await engine.get_project(project_id)
            length_check = _chapter_length_check(project, prose)
            yield _sse_event("stage", {"stage": "finalizing", "message": "正文已生成，正在保存候选版本"})
            repetition = scan_chapter_repetition(
                chapter_number=number,
                content=prose,
                chapters=await engine.chapters.list(project_id),
            )
            plan = await engine.uow.chapter_plans.latest_for_chapter(
                (await engine.chapters.get_by_number(project_id, number)).id
            )
            scenes = await engine.scene_plans.list(plan.id) if plan else []
            relevance = scan_chapter_relevance(content=prose, plan=plan, scenes=scenes) if plan else None
            pipeline = await _pipeline(engine, workflow, project_id)
            if body.persist:
                await pipeline.persist_revision(
                    project_id,
                    number,
                    prose,
                    created_by=actor.id,
                    change_summary="writer-agent streamed candidate",
                )
                chapter_row = await engine.chapters.get_by_number(project_id, number)
                metadata = dict(chapter_row.extra_metadata or {})
                metadata["audit"] = {
                    **(metadata.get("audit") or {}),
                    "status": "streamed" if length_check["ok"] else "length_failed",
                    "versions": [{
                        "version": 1,
                        "prose": prose,
                        "word_count": count_text_units(prose),
                        "score": None,
                        "selected": True,
                        "accepted": True,
                    }],
                    "content_fingerprint": _content_fingerprint(chapter_row.content),
                    "length_check": length_check,
                }
                await engine.chapters.update(chapter_row.model_copy(update={"extra_metadata": metadata}))
                await save_project_snapshot(engine, project_id)
            repetition_payload = repetition.model_dump(mode="json")
            relevance_payload = relevance.model_dump(mode="json") if relevance else {"status": "missing_plan", "blocked": True}
            yield _sse_event("done", {
                "writer": {"title": context.chapter_plan.chapter_title, "prose": prose, "word_count": count_text_units(prose)},
                "editor": {"overall_notes": "流式正文已生成，等待系统审核"},
                "continuity": {"overall": "pending"},
                "review_status": "streaming_complete",
                "versions": [{"version": 1, "prose": prose, "word_count": count_text_units(prose), "score": None, "selected": True, "accepted": True}],
                "length_warning": (
                    None
                    if length_check["ok"]
                    else f"正文当前为 {length_check['count']}，目标范围为 "
                    f"{length_check['minimum']}-{length_check['maximum']}"
                ),
                "length_check": length_check,
                "repetition_check": repetition_payload,
                "relevance_check": relevance_payload,
                "auto_approved": False,
            })
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/projects/{project_id}/chapters/{number}/review")
async def review_chapter(
    project_id: UUID,
    number: int,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    review_workflow: Annotated[AgentWorkflow | None, Depends(get_review_workflow)],
):
    context = await _writer_context(engine, project_id, number)
    chapter = await engine.chapters.get_by_number(project_id, number)
    project = await engine.get_project(project_id)
    length_check = _chapter_length_check(project, chapter.content)
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
    if (
        repetition_check.blocked
        or (relevance_check and relevance_check.blocked)
        or plan is None
        or not length_check["ok"]
    ):
        metadata = dict(chapter.extra_metadata or {})
        metadata["audit"] = {
            **(metadata.get("audit") or {}),
            "status": "failed",
            "repetition_check": repetition_check.model_dump(),
            "relevance_check": relevance_check.model_dump() if relevance_check else {"status": "missing_plan", "blocked": True},
            "length_check": length_check,
        }
        blocked = await engine.chapters.update(chapter.model_copy(update={"extra_metadata": metadata}))
        return {
            "chapter": blocked,
            "reviewed": False,
            "blocked_by_repetition": repetition_check.blocked,
            "blocked_by_relevance": bool(plan is None or (relevance_check and relevance_check.blocked)),
            "blocked_by_length": not length_check["ok"],
            "repetition_check": repetition_check,
            "relevance_check": relevance_check,
            "length_check": length_check,
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
        overall=escalate_verdict(continuity_result.output.overall, [
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
            *scan_prose_completeness(chapter.content),
        ]),
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
            *scan_prose_completeness(chapter.content),
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
            overall=escalate_verdict(continuity.overall, [*continuity.findings, *secondary.findings]),
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
    if continuity.overall is ContinuityVerdict.ERROR or editor_blocked or commercial_blocked or not length_check["ok"]:
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
            "length_check": length_check,
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
            "blocked_by_length": not length_check["ok"],
        }
    metadata = dict(chapter.extra_metadata or {})
    metadata["audit"] = {
        **(metadata.get("audit") or {}),
        "status": "passed",
        "independent_review": getattr(review_workflow, "provider_identity", None),
        "independent_commercial": commercial.model_dump() if commercial else None,
        "content_fingerprint": _content_fingerprint(chapter.content),
        "length_check": length_check,
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
        overall=escalate_verdict(result.output.overall, [
            *result.output.findings,
            *alignment,
            *local_signals,
            *scan_commercial_quality(prose=chapter.content, context=context),
            *scan_prose_completeness(chapter.content),
        ]),
        findings=[
            *result.output.findings,
            *alignment,
            *local_signals,
            *scan_commercial_quality(prose=chapter.content, context=context),
            *scan_prose_completeness(chapter.content),
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
    prior_audit = metadata.get("audit") or {}
    continuity_blocked = (
        continuity.overall is ContinuityVerdict.ERROR
        or repetition_check.blocked
        or plan is None
        or (relevance_check and relevance_check.blocked)
    )
    metadata["audit"] = {
        **prior_audit,
        "status": "failed" if continuity_blocked else "passed" if prior_audit.get("status") == "passed" else "completed",
        "repetition_check": repetition_check.model_dump(),
        "relevance_check": relevance_check.model_dump() if relevance_check else {"status": "missing_plan", "blocked": True},
        "content_fingerprint": _content_fingerprint(chapter.content),
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
    chapter = await engine.chapters.get_by_number(project_id, number)
    audit = dict(chapter.extra_metadata or {}).get("audit") or {}
    length_check = _chapter_length_check(await engine.get_project(project_id), chapter.content)
    if audit.get("status") != "passed":
        raise InvalidStateError("当前章节没有通过独立审查，不能批准")
    if not length_check["ok"]:
        raise InvalidStateError(
            f"当前章节字数为 {length_check['count']}，必须在 "
            f"{length_check['minimum']}-{length_check['maximum']} 范围内才能批准"
        )
    if audit.get("content_fingerprint") != _content_fingerprint(chapter.content):
        raise InvalidStateError("独立审查针对的正文版本已变化，请重新审查")
    pipeline = await _pipeline(engine, workflow, project_id, review_workflow=review_workflow)
    result = await pipeline.commit_approved_chapter(
        project_id,
        number,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )
    session = getattr(engine.uow, "session", None)
    if isinstance(session, AsyncSession):
        try:
            await persist_commit(session, project_id, result.chapter.id, pipeline, result)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    await save_project_snapshot(engine, project_id)
    return result.chapter


async def _pipeline(
    engine: NovelEngine,
    workflow: AgentWorkflow,
    project_id: UUID,
    *,
    review_workflow: AgentWorkflow | None = None,
) -> ChapterGenerationPipeline:
    memory = MemoryService(async_embedder=ProviderEmbedder(workflow.provider))
    history = None
    session = getattr(engine.uow, "session", None)
    if isinstance(session, AsyncSession):
        history = await hydrate_pipeline_memory(session, project_id, memory)
    history = await hydrate_draft_expression_history(engine, project_id, history or StyleHistory())
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
        creative_contract=contract_for_project(project),
    )


def _severity(verdict: ContinuityVerdict) -> ContinuitySeverity:
    if verdict is ContinuityVerdict.ERROR:
        return ContinuitySeverity.HIGH
    if verdict is ContinuityVerdict.WARNING:
        return ContinuitySeverity.MEDIUM
    return ContinuitySeverity.LOW
