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
            known_by=list(row.known_by or []),
            unknown_to=list(row.unknown_to or []),
            extra_metadata=row.extra_metadata or {},
        )
        for row in rows
    ]


@router.get("/projects/{project_id}/memory/preflight")
async def memory_backfill_preflight(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    """Read-only safety check before historical memory backfill."""
    await engine.get_project(project_id)
    chapters = sorted(await engine.chapters.list(project_id), key=lambda item: item.chapter_number)
    approved = [item for item in chapters if item.status.value in {"approved", "published"}]
    empty_approved = [item.chapter_number for item in approved if not item.content.strip()]
    missing_plans: list[int] = []
    missing_scenes: list[int] = []
    for chapter in approved:
        plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
        if plan is None:
            missing_plans.append(chapter.chapter_number)
            continue
        if not await engine.scene_plans.list(plan.id):
            missing_scenes.append(chapter.chapter_number)
    session = getattr(engine.uow, "session", None)
    memory_chapters: set[int] = set()
    if isinstance(session, AsyncSession):
        rows = (
            await session.scalars(select(StoryMemory).where(StoryMemory.project_id == project_id))
        ).all()
        memory_chapters = {
            row.chapter_number
            for row in rows
            if row.chapter_number is not None and (row.extra_metadata or {}).get("kind") == "chapter_memory"
        }
    missing_memory = [item.chapter_number for item in approved if item.chapter_number not in memory_chapters]
    blockers: list[str] = []
    if not approved:
        blockers.append("没有已批准章节，当前没有可回填的真实章节")
    if empty_approved:
        blockers.append(f"已批准但正文为空：{empty_approved}")
    if missing_plans:
        blockers.append(f"缺少章节计划：{missing_plans}")
    if missing_scenes:
        blockers.append(f"缺少场景计划：{missing_scenes}")
    return {
        "read_only": True,
        "safe_to_backfill": bool(approved) and not blockers,
        "total_chapters": len(chapters),
        "approved_chapters": [item.chapter_number for item in approved],
        "memory_chapters": sorted(memory_chapters),
        "missing_memory": missing_memory,
        "empty_approved": empty_approved,
        "missing_plans": missing_plans,
        "missing_scenes": missing_scenes,
        "blockers": blockers,
    }


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
