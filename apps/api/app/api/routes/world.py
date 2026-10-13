from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import Actor, confirmed_by, get_actor, get_engine
from app.api.schemas import ConfirmBody, WorldPatch
from app.services.book_snapshot import save_project_snapshot
from novel_engine.domain.errors import NotFoundError
from novel_engine.models.entities import WorldBible, WorldRule
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["world"])


@router.get("/projects/{project_id}/world")
async def get_world(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> WorldBible:
    bible = await engine.world_bibles.get(project_id)
    if bible is None:
        raise NotFoundError("world bible not found")
    return bible


@router.patch("/projects/{project_id}/world")
async def patch_world(
    project_id: UUID,
    body: WorldPatch,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> WorldBible:
    existing = await engine.world_bibles.get(project_id)
    bible_id = existing.id if existing else WorldBible(project_id=project_id, name=body.name, summary=body.summary).id
    rules = [
        WorldRule(
            world_bible_id=bible_id,
            name=item.name,
            category=item.category,
            description=item.description,
            is_hard_constraint=item.is_hard_constraint,
        )
        for item in body.rules
    ]
    payload = WorldBible(
        id=bible_id,
        project_id=project_id,
        name=body.name,
        summary=body.summary,
        geography=body.geography,
        factions=body.factions,
        rules=rules,
    )
    world = await engine.world_bibles.upsert(payload)
    await save_project_snapshot(engine, project_id)
    return world


@router.post("/projects/{project_id}/world/submit")
async def submit_world(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> WorldBible:
    world = await engine.world_bibles.submit_for_review(project_id)
    await save_project_snapshot(engine, project_id)
    return world


@router.post("/projects/{project_id}/world/approve")
async def approve_world(
    project_id: UUID,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    actor: Annotated[Actor, Depends(get_actor)],
) -> WorldBible:
    world = await engine.world_bibles.approve(
        project_id,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )
    await save_project_snapshot(engine, project_id)
    return world
