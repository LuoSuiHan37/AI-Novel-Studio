from __future__ import annotations

import uuid

from novel_engine.domain import approval
from novel_engine.domain.errors import DuplicateError, InvalidStateError, NotFoundError
from novel_engine.models.entities import Character
from novel_engine.models.enums import ApprovalStatus, CharacterRole
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class CharacterService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, character_id: uuid.UUID) -> Character:
        character = await self._uow.characters.get(character_id)
        if character is None:
            raise NotFoundError("character not found")
        return character

    async def list(self, project_id: uuid.UUID) -> list[Character]:
        await require_project(self._uow, project_id)
        return await self._uow.characters.list_by_project(project_id)

    async def create(self, character: Character) -> Character:
        await require_project(self._uow, character.project_id)
        _validate_character(character)
        existing = await self._uow.characters.list_by_project(character.project_id)
        if any(item.name.lower() == character.name.lower() for item in existing):
            raise DuplicateError(f"character already exists: {character.name}")
        # Characters are structural writing data, not a human approval gate.
        # A valid character becomes available immediately after creation.
        character.status = ApprovalStatus.APPROVED
        saved = await self._uow.characters.save(character)
        await self._uow.commit()
        return saved

    async def update(self, character: Character) -> Character:
        current = await self.get(character.id)
        if current.project_id != character.project_id:
            raise InvalidStateError("cannot move a character to another project")
        _validate_character(character)
        # Editing a character should not send the project back through an
        # approval step either; keep it immediately usable by generation.
        character.status = ApprovalStatus.APPROVED
        saved = await self._uow.characters.save(character)
        await self._uow.commit()
        return saved

    async def submit_for_review(self, character_id: uuid.UUID) -> Character:
        character = await self.get(character_id)
        # Kept as a backwards-compatible no-op for older clients that still
        # call the former review endpoint.
        if character.status is ApprovalStatus.APPROVED:
            return character
        approval.submit_for_review(character)
        saved = await self._uow.characters.save(character)
        await self._uow.commit()
        return saved

    async def approve(self, character_id: uuid.UUID, *, confirmed_by: str) -> Character:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        character = await self.get(character_id)
        if character.status is ApprovalStatus.APPROVED:
            return character
        approval.approve(character)
        saved = await self._uow.characters.save(character)
        await self._uow.commit()
        return saved

    async def delete(self, character_id: uuid.UUID) -> None:
        character = await self.get(character_id)
        if character.status is ApprovalStatus.APPROVED:
            raise InvalidStateError("approved characters cannot be deleted; reopen and reject first")
        await self._uow.characters.delete(character_id)
        await self._uow.commit()


def _validate_character(character: Character) -> None:
    required = {
        "personality": character.personality,
        "background": character.background,
        "goal": character.goal,
        "motivation": character.motivation,
        "fear": character.fear,
        "secret": character.secret,
        "strength": character.strength,
        "weakness": character.weakness,
        "internal_conflict": character.internal_conflict,
        "external_conflict": character.external_conflict,
        "speech_style": character.speech_style,
        "character_arc": character.character_arc,
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise InvalidStateError(f"character is missing fields: {', '.join(missing)}")
    if character.role is CharacterRole.PROTAGONIST and not character.character_arc.strip():
        raise InvalidStateError("protagonist requires a character_arc")
