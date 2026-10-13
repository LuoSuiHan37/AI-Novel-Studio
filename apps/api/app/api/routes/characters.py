from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import Actor, confirmed_by, get_actor, get_engine
from app.api.schemas import CharacterCreate, CharacterPatch, ConfirmBody
from app.services.book_snapshot import save_project_snapshot
from novel_engine.domain.errors import NotFoundError
from novel_engine.models.entities import Character
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["characters"])


@router.get("/projects/{project_id}/characters")
async def list_characters(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> list[Character]:
    return await engine.characters.list(project_id)


@router.post("/projects/{project_id}/characters", status_code=status.HTTP_201_CREATED)
async def create_character(
    project_id: UUID,
    body: CharacterCreate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> Character:
    character = await engine.characters.create(Character(project_id=project_id, **body.model_dump()))
    await save_project_snapshot(engine, project_id)
    return character


@router.get("/projects/{project_id}/characters/{character_id}")
async def get_character(
    project_id: UUID,
    character_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> Character:
    character = await engine.characters.get(character_id)
    if character.project_id != project_id:
        raise NotFoundError("character not found")
    return character


@router.patch("/projects/{project_id}/characters/{character_id}")
async def patch_character(
    project_id: UUID,
    character_id: UUID,
    body: CharacterPatch,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> Character:
    current = await get_character(project_id, character_id, engine)
    character = await engine.characters.update(current.model_copy(update=body.model_dump(exclude_unset=True)))
    await save_project_snapshot(engine, project_id)
    return character


@router.post("/projects/{project_id}/characters/{character_id}/submit")
async def submit_character(
    project_id: UUID,
    character_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> Character:
    await get_character(project_id, character_id, engine)
    character = await engine.characters.submit_for_review(character_id)
    await save_project_snapshot(engine, project_id)
    return character


@router.post("/projects/{project_id}/characters/{character_id}/approve")
async def approve_character(
    project_id: UUID,
    character_id: UUID,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    actor: Annotated[Actor, Depends(get_actor)],
) -> Character:
    await get_character(project_id, character_id, engine)
    character = await engine.characters.approve(
        character_id,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )
    await save_project_snapshot(engine, project_id)
    return character


@router.delete("/projects/{project_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    project_id: UUID,
    character_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> Response:
    await get_character(project_id, character_id, engine)
    await engine.characters.delete(character_id)
    await save_project_snapshot(engine, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
