from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, confirmed_by, get_actor, get_engine
from app.api.schemas import ConfirmBody, PlotPatch
from app.services.book_snapshot import save_project_snapshot
from novel_engine.domain.errors import NotFoundError
from novel_engine.models.entities import MasterPlot, PlotBeat
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["plot"])


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
