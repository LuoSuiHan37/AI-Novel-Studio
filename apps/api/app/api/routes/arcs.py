from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import Actor, confirmed_by, get_actor, get_engine
from app.api.schemas import ArcCreate, ArcPatch, ConfirmBody
from app.services.book_snapshot import save_project_snapshot
from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import StoryArc
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["arcs"])


@router.get("/projects/{project_id}/arcs")
async def list_arcs(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> list[StoryArc]:
    return await engine.story_arcs.list(project_id)


@router.post("/projects/{project_id}/arcs", status_code=status.HTTP_201_CREATED)
async def create_arc(
    project_id: UUID,
    body: ArcCreate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> StoryArc:
    plot_id = body.master_plot_id
    if plot_id is None:
        plots = await engine.master_plots.list(project_id)
        active = next((item for item in plots if item.is_active), plots[0] if plots else None)
        if active is None:
            raise InvalidStateError("create a master plot before adding arcs")
        plot_id = active.id
    arc = await engine.story_arcs.create(
        StoryArc(
            project_id=project_id,
            master_plot_id=plot_id,
            title=body.title,
            arc_type=body.arc_type,
            sequence=body.sequence,
            summary=body.summary,
            start_chapter_number=body.start_chapter_number,
            end_chapter_number=body.end_chapter_number,
        )
    )
    await save_project_snapshot(engine, project_id)
    return arc


@router.patch("/projects/{project_id}/arcs/{arc_id}")
async def patch_arc(
    project_id: UUID,
    arc_id: UUID,
    body: ArcPatch,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> StoryArc:
    current = await engine.story_arcs.get(arc_id)
    if current.project_id != project_id:
        raise NotFoundError("story arc not found")
    arc = await engine.story_arcs.update(current.model_copy(update=body.model_dump(exclude_unset=True)))
    await save_project_snapshot(engine, project_id)
    return arc


@router.post("/projects/{project_id}/arcs/{arc_id}/submit")
async def submit_arc(
    project_id: UUID,
    arc_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> StoryArc:
    current = await engine.story_arcs.get(arc_id)
    if current.project_id != project_id:
        raise NotFoundError("story arc not found")
    arc = await engine.story_arcs.submit_for_review(arc_id)
    await save_project_snapshot(engine, project_id)
    return arc


@router.post("/projects/{project_id}/arcs/{arc_id}/approve")
async def approve_arc(
    project_id: UUID,
    arc_id: UUID,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    actor: Annotated[Actor, Depends(get_actor)],
) -> StoryArc:
    current = await engine.story_arcs.get(arc_id)
    if current.project_id != project_id:
        raise NotFoundError("story arc not found")
    arc = await engine.story_arcs.approve(
        arc_id,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )
    await save_project_snapshot(engine, project_id)
    return arc


@router.delete("/projects/{project_id}/arcs/{arc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_arc(
    project_id: UUID,
    arc_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> Response:
    current = await engine.story_arcs.get(arc_id)
    if current.project_id != project_id:
        raise NotFoundError("story arc not found")
    await engine.story_arcs.delete(arc_id)
    await save_project_snapshot(engine, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
