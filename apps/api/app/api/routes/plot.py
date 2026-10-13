from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, confirmed_by, get_actor, get_engine, get_workflow
from app.api.schemas import ArchitectureApply, ConfirmBody, PlotPatch
from app.services.book_snapshot import save_project_snapshot
from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.agents.contracts import OutlineInput, OutlineOutput
from novel_engine.models.entities import MasterPlot, PlotBeat, StoryArc
from novel_engine.workflows.context import character_to_agent, story_bible_to_architect, world_bible_to_agent
from novel_engine.workflows.agent_workflow import AgentWorkflow
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["plot"])


def _validate_architecture_payload(project, body: ArchitectureApply) -> None:
    target = project.chapter_count_target
    if target is None:
        raise InvalidStateError("a planned chapter count is required before applying architecture")
    if len(body.beats) < 3:
        raise InvalidStateError("architecture must contain at least three master-plot beats")
    if not body.arcs:
        raise InvalidStateError("architecture must contain at least one story arc")
    sequences = [item.sequence for item in body.arcs]
    if len(sequences) != len(set(sequences)):
        raise InvalidStateError("story arc sequence numbers must be unique")
    ranges = []
    for item in body.arcs:
        start = item.start_chapter_number or 1
        end = item.end_chapter_number or target
        if start < 1 or end > target or end < start:
            raise InvalidStateError(f"story arc {item.title!r} is outside chapters 1-{target}")
        ranges.append((start, end))
    missing = [
        number for number in range(1, target + 1)
        if not any(start <= number <= end for start, end in ranges)
    ]
    if missing:
        preview = ", ".join(str(item) for item in missing[:8])
        raise InvalidStateError(f"story arcs do not cover planned chapters: {preview}")
    hints = [item.chapter_hint for item in body.beats if item.chapter_hint is not None]
    if any(hint < 1 or hint > target for hint in hints):
        raise InvalidStateError("master-plot beat chapter hints must be within the planned chapter range")


async def _active_plot(engine: NovelEngine, project_id: UUID) -> MasterPlot | None:
    plots = await engine.master_plots.list(project_id)
    for item in plots:
        if item.is_active:
            return item
    return plots[0] if plots else None


@router.get("/projects/{project_id}/plot")
async def get_plot(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> MasterPlot:
    plot = await _active_plot(engine, project_id)
    if plot is None:
        raise NotFoundError("master plot not found")
    return plot


@router.post("/projects/{project_id}/architecture-suggestion")
async def suggest_architecture(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
) -> OutlineOutput:
    """Generate a complete-book outline as a preview; it is not persisted yet."""
    project = await engine.get_project(project_id)
    bible = await engine.story_bibles.get(project_id)
    world = await engine.world_bibles.get(project_id)
    characters = await engine.characters.list(project_id)
    if bible is None or world is None or not characters:
        raise NotFoundError("story bible, world bible, and at least one character are required")
    proposal = await workflow.propose_outline(
        OutlineInput(
            story_bible=story_bible_to_architect(bible),
            characters=[character_to_agent(item) for item in characters],
            world=world_bible_to_agent(world),
            target_chapter_count=project.chapter_count_target or 120,
        )
    )
    if len(proposal.output.beats) < 3:
        raise NotFoundError("AI architecture must contain at least three beats; please retry")
    return proposal.output


@router.post("/projects/{project_id}/architecture/apply")
async def apply_architecture(
    project_id: UUID,
    body: ArchitectureApply,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    """Persist a reviewed architecture without deleting existing approved arcs."""
    project = await engine.get_project(project_id)
    _validate_architecture_payload(project, body)
    plot_body = PlotPatch(
        title=body.title,
        structure=body.structure,
        summary=body.summary,
        beats=body.beats,
        is_active=True,
    )
    current = await _active_plot(engine, project_id)
    payload = MasterPlot(
        project_id=project_id,
        title=plot_body.title,
        structure=plot_body.structure,
        summary=plot_body.summary,
        beats=[PlotBeat(**item.model_dump()) for item in plot_body.beats],
        is_active=True,
    )
    plot = await engine.master_plots.update(payload.model_copy(update={"id": current.id})) if current else await engine.master_plots.create(payload)
    existing = await engine.story_arcs.list(project_id)
    saved_arcs = []
    for item in body.arcs:
        matching = next((arc for arc in existing if arc.sequence == item.sequence), None)
        arc_payload = StoryArc(
            project_id=project_id,
            master_plot_id=plot.id,
            title=item.title,
            arc_type=item.arc_type,
            sequence=item.sequence,
            summary=item.summary,
            start_chapter_number=item.start_chapter_number,
            end_chapter_number=item.end_chapter_number,
        )
        if matching is not None:
            saved_arcs.append(await engine.story_arcs.update(arc_payload.model_copy(update={"id": matching.id})))
        else:
            saved_arcs.append(await engine.story_arcs.create(arc_payload))
    await save_project_snapshot(engine, project_id)
    return {"plot": plot, "arcs": saved_arcs, "preserved_existing_arcs": max(0, len(existing) - len(body.arcs))}


@router.patch("/projects/{project_id}/plot")
async def patch_plot(
    project_id: UUID,
    body: PlotPatch,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> MasterPlot:
    payload = MasterPlot(
        project_id=project_id,
        title=body.title,
        structure=body.structure,
        summary=body.summary,
        beats=[PlotBeat(**item.model_dump()) for item in body.beats],
        is_active=body.is_active,
    )
    current = await _active_plot(engine, project_id)
    if current is None:
        plot = await engine.master_plots.create(payload)
    else:
        plot = await engine.master_plots.update(payload.model_copy(update={"id": current.id}))
    await save_project_snapshot(engine, project_id)
    return plot


@router.post("/projects/{project_id}/plot/submit")
async def submit_plot(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> MasterPlot:
    plot = await _active_plot(engine, project_id)
    if plot is None:
        raise NotFoundError("master plot not found")
    plot = await engine.master_plots.submit_for_review(plot.id)
    await save_project_snapshot(engine, project_id)
    return plot


@router.post("/projects/{project_id}/plot/approve")
async def approve_plot(
    project_id: UUID,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    actor: Annotated[Actor, Depends(get_actor)],
) -> MasterPlot:
    plot = await _active_plot(engine, project_id)
    if plot is None:
        raise NotFoundError("master plot not found")
    plot = await engine.master_plots.approve(
        plot.id,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )
    await save_project_snapshot(engine, project_id)
    return plot
