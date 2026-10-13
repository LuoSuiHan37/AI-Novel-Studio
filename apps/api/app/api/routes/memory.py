from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_engine
from app.api.schemas import MemoryItemOut, TimelineItemOut
from app.db.models.memory import StoryMemory, TimelineEvent
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["memory"])


@router.get("/projects/{project_id}/memory")
async def list_memory(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> list[MemoryItemOut]:
    await engine.get_project(project_id)
    session = getattr(engine.uow, "session", None)
    if not isinstance(session, AsyncSession):
        return []
    rows = (
        await session.scalars(select(StoryMemory).where(StoryMemory.project_id == project_id))
    ).all()
    return [
        MemoryItemOut(
            id=row.id,
            layer=row.layer,
            epistemic_status=row.epistemic_status,
            memory_type=row.memory_type,
            importance=row.importance,
            content=row.content,
            chapter_number=row.chapter_number,
            location=row.location,
        )
        for row in rows
    ]


@router.get("/projects/{project_id}/timeline")
async def list_timeline(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> list[TimelineItemOut]:
    await engine.get_project(project_id)
    session = getattr(engine.uow, "session", None)
    if not isinstance(session, AsyncSession):
        return []
    rows = (
        await session.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.project_id == project_id)
            .order_by(TimelineEvent.sequence)
        )
    ).all()
    return [
        TimelineItemOut(
            id=row.id,
            sequence=row.sequence,
            in_world_time=row.in_world_time,
            title=row.title,
            description=row.description,
            location=row.location,
        )
        for row in rows
    ]


@router.get("/projects/{project_id}/hooks")
async def list_hooks(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    return await engine.hooks.list(project_id)


@router.get("/projects/{project_id}/foreshadowing")
async def list_foreshadowing(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    return await engine.foreshadowings.list(project_id)
