from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Actor, confirmed_by, get_actor, get_engine
from app.api.schemas import ConfirmBody, StoryPatch
from app.services.book_snapshot import save_project_snapshot
from novel_engine.domain.errors import NotFoundError
from novel_engine.models.entities import StoryBible
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["story"])


@router.get("/projects/{project_id}/story")
async def get_story(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> StoryBible:
    bible = await engine.story_bibles.get(project_id)
    if bible is None:
        raise NotFoundError("story bible not found")
    return bible


@router.patch("/projects/{project_id}/story")
async def patch_story(
    project_id: UUID,
    body: StoryPatch,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> StoryBible:
    values = body.model_dump()
    if any(
        key in body.model_fields_set
        for key in ("target_reader", "reading_tags", "content_tags", "protagonist_names")
    ):
        synopsis_length = len((body.synopsis or "").strip())
        if not 50 <= synopsis_length <= 500:
            raise HTTPException(status_code=422, detail="番茄作品简介必须为 50–500 字")
        if len(body.protagonist_names) > 2 or any(len(name.strip()) > 5 for name in body.protagonist_names):
            raise HTTPException(status_code=422, detail="番茄主角名最多两位，每个名字不超过 5 个字")
    fanqie_submission = {
        "target_reader": values.pop("target_reader", "female"),
        "reading_tags": values.pop("reading_tags", []),
        "content_tags": values.pop("content_tags", []),
        "protagonist_names": values.pop("protagonist_names", []),
    }
    existing = await engine.story_bibles.get(project_id)
    metadata = dict(existing.extra_metadata or {}) if existing else {}
    metadata["fanqie_submission"] = fanqie_submission
    story = await engine.story_bibles.upsert(
        StoryBible(project_id=project_id, extra_metadata=metadata, **values)
    )
    await save_project_snapshot(engine, project_id)
    return story


@router.post("/projects/{project_id}/story/submit")
async def submit_story(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> StoryBible:
    story = await engine.story_bibles.submit_for_review(project_id)
    await save_project_snapshot(engine, project_id)
    return story


@router.post("/projects/{project_id}/story/approve")
async def approve_story(
    project_id: UUID,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    actor: Annotated[Actor, Depends(get_actor)],
) -> StoryBible:
    story = await engine.story_bibles.approve(
        project_id,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )
    await save_project_snapshot(engine, project_id)
    return story
