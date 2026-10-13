from __future__ import annotations

import uuid

from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import Foreshadowing
from novel_engine.models.enums import ForeshadowStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class ForeshadowingService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, item_id: uuid.UUID) -> Foreshadowing:
        item = await self._uow.foreshadowings.get(item_id)
        if item is None:
            raise NotFoundError("foreshadowing not found")
        return item

    async def list(self, project_id: uuid.UUID, *, unpaid_only: bool = False) -> list[Foreshadowing]:
        await require_project(self._uow, project_id)
        items = await self._uow.foreshadowings.list_by_project(project_id)
        if unpaid_only:
            return [
                item
                for item in items
                if item.status not in {ForeshadowStatus.PAID_OFF, ForeshadowStatus.DROPPED}
            ]
        return items

    async def create(self, item: Foreshadowing) -> Foreshadowing:
        await require_project(self._uow, item.project_id)
        if not item.description.strip():
            raise InvalidStateError("foreshadowing description is required")
        item = item.model_copy(update={"status": ForeshadowStatus.PLANNED})
        saved = await self._uow.foreshadowings.save(item)
        await self._uow.commit()
        return saved

    async def plant(self, item_id: uuid.UUID, setup_chapter_id: uuid.UUID) -> Foreshadowing:
        item = await self.get(item_id)
        await self._require_chapter(item.project_id, setup_chapter_id)
        item = item.model_copy(
            update={"setup_chapter_id": setup_chapter_id, "status": ForeshadowStatus.PLANTED}
        )
        saved = await self._uow.foreshadowings.save(item)
        await self._uow.commit()
        return saved

    async def set_expected_payoff(self, item_id: uuid.UUID, chapter_id: uuid.UUID) -> Foreshadowing:
        item = await self.get(item_id)
        await self._require_chapter(item.project_id, chapter_id)
        item = item.model_copy(update={"expected_payoff_chapter_id": chapter_id})
        saved = await self._uow.foreshadowings.save(item)
        await self._uow.commit()
        return saved

    async def confirm_payoff(
        self,
        item_id: uuid.UUID,
        actual_payoff_chapter_id: uuid.UUID,
        *,
        confirmed_by: str,
    ) -> Foreshadowing:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required to mark a payoff")
        item = await self.get(item_id)
        await self._require_chapter(item.project_id, actual_payoff_chapter_id)
        if item.status is not ForeshadowStatus.PLANTED:
            raise InvalidStateError("only planted foreshadowing can be paid off")
        item = item.model_copy(
            update={
                "actual_payoff_chapter_id": actual_payoff_chapter_id,
                "status": ForeshadowStatus.PAID_OFF,
            }
        )
        saved = await self._uow.foreshadowings.save(item)
        await self._uow.commit()
        return saved

    async def mark_missed(self, item_id: uuid.UUID, *, confirmed_by: str) -> Foreshadowing:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        item = await self.get(item_id)
        item = item.model_copy(update={"status": ForeshadowStatus.MISSED})
        saved = await self._uow.foreshadowings.save(item)
        await self._uow.commit()
        return saved

    async def drop(self, item_id: uuid.UUID, *, confirmed_by: str) -> Foreshadowing:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        item = await self.get(item_id)
        item = item.model_copy(update={"status": ForeshadowStatus.DROPPED})
        saved = await self._uow.foreshadowings.save(item)
        await self._uow.commit()
        return saved

    async def _require_chapter(self, project_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
        chapter = await self._uow.chapters.get(chapter_id)
        if chapter is None or chapter.project_id != project_id:
            raise NotFoundError("chapter not found in this project")
