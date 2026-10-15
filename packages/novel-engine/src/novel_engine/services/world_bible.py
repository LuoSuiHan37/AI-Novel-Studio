from __future__ import annotations

import uuid

from novel_engine.domain import approval
from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import WorldBible, WorldRule, new_id
from novel_engine.models.enums import ApprovalStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class WorldBibleService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, project_id: uuid.UUID) -> WorldBible | None:
        await require_project(self._uow, project_id)
        return await self._uow.world_bibles.get_by_project(project_id)

    async def upsert(self, bible: WorldBible, *, commit: bool = True) -> WorldBible:
        await require_project(self._uow, bible.project_id)
        if not bible.name.strip() or not bible.summary.strip():
            raise InvalidStateError("world name and summary are required")
        existing = await self._uow.world_bibles.get_by_project(bible.project_id)
        if existing is not None:
            bible.id = existing.id
            bible.rules = existing.rules if not bible.rules else bible.rules
        bible.status = ApprovalStatus.APPROVED
        saved = await self._uow.world_bibles.save(bible)
        if commit:
            await self._uow.commit()
        return saved

    async def add_rule(self, project_id: uuid.UUID, rule: WorldRule) -> WorldBible:
        bible = await self._require(project_id)
        if rule.world_bible_id != bible.id:
            rule = rule.model_copy(update={"world_bible_id": bible.id, "id": rule.id or new_id()})
        if not rule.name.strip() or not rule.description.strip():
            raise InvalidStateError("world rule name and description are required")
        rules = [item for item in bible.rules if item.id != rule.id]
        rules.append(rule)
        bible = bible.model_copy(update={"rules": rules, "status": ApprovalStatus.APPROVED})
        saved = await self._uow.world_bibles.save(bible)
        await self._uow.commit()
        return saved

    async def submit_for_review(self, project_id: uuid.UUID) -> WorldBible:
        bible = await self._require(project_id)
        if bible.status is ApprovalStatus.APPROVED:
            return bible
        if not bible.rules:
            raise InvalidStateError("add at least one world rule before review")
        approval.submit_for_review(bible)
        saved = await self._uow.world_bibles.save(bible)
        await self._uow.commit()
        return saved

    async def approve(self, project_id: uuid.UUID, *, confirmed_by: str) -> WorldBible:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        bible = await self._require(project_id)
        if bible.status is ApprovalStatus.APPROVED:
            return bible
        approval.approve(bible)
        saved = await self._uow.world_bibles.save(bible)
        await self._uow.commit()
        return saved

    async def _require(self, project_id: uuid.UUID) -> WorldBible:
        bible = await self.get(project_id)
        if bible is None:
            raise NotFoundError("world bible not found")
        return bible
