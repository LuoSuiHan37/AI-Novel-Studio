from __future__ import annotations

import uuid

from novel_engine.domain import approval
from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import StoryBible, touch
from novel_engine.models.enums import ApprovalStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class StoryBibleService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, project_id: uuid.UUID) -> StoryBible | None:
        await require_project(self._uow, project_id)
        return await self._uow.story_bibles.get_by_project(project_id)

    async def upsert(self, bible: StoryBible) -> StoryBible:
        await require_project(self._uow, bible.project_id)
        _validate_bible(bible)
        existing = await self._uow.story_bibles.get_by_project(bible.project_id)
        if existing is not None:
            bible.id = existing.id
        bible.status = ApprovalStatus.APPROVED
        saved = await self._uow.story_bibles.save(bible)
        await self._uow.commit()
        return saved

    async def submit_for_review(self, project_id: uuid.UUID) -> StoryBible:
        bible = await self._require(project_id)
        if bible.status is ApprovalStatus.APPROVED:
            return bible
        approval.submit_for_review(bible)
        saved = await self._uow.story_bibles.save(bible)
        await self._uow.commit()
        return saved

    async def approve(self, project_id: uuid.UUID, *, confirmed_by: str) -> StoryBible:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        bible = await self._require(project_id)
        if bible.status is ApprovalStatus.APPROVED:
            return bible
        approval.approve(bible)
        saved = await self._uow.story_bibles.save(bible)
        await self._uow.commit()
        return saved

    async def reject(self, project_id: uuid.UUID, *, confirmed_by: str, note: str | None = None) -> StoryBible:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        bible = await self._require(project_id)
        approval.reject(bible)
        touch(bible)
        saved = await self._uow.story_bibles.save(bible)
        await self._uow.commit()
        return saved

    async def _require(self, project_id: uuid.UUID) -> StoryBible:
        bible = await self.get(project_id)
        if bible is None:
            raise NotFoundError("story bible not found")
        return bible


def _validate_bible(bible: StoryBible) -> None:
    if bible.target_word_count < 10_000:
        raise InvalidStateError("target_word_count must be at least 10000 for a long-form serial")
    if bible.chapter_word_count < 500:
        raise InvalidStateError("chapter_word_count must be at least 500")
    if not bible.premise.strip() or not bible.theme.strip():
        raise InvalidStateError("premise and theme are required")
