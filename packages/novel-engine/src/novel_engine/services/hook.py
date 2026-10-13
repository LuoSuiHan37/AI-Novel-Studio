from __future__ import annotations

import uuid

from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import Hook
from novel_engine.models.enums import HookStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class HookService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, hook_id: uuid.UUID) -> Hook:
        hook = await self._uow.hooks.get(hook_id)
        if hook is None:
            raise NotFoundError("hook not found")
        return hook

    async def list(self, project_id: uuid.UUID, *, open_only: bool = False) -> list[Hook]:
        await require_project(self._uow, project_id)
        items = await self._uow.hooks.list_by_project(project_id)
        if open_only:
            return [item for item in items if item.status not in {HookStatus.RESOLVED, HookStatus.DROPPED}]
        return items

    async def create(self, hook: Hook) -> Hook:
        await require_project(self._uow, hook.project_id)
        if not hook.description.strip():
            raise InvalidStateError("hook description is required")
        hook = hook.model_copy(update={"status": HookStatus.PLANNED})
        saved = await self._uow.hooks.save(hook)
        await self._uow.commit()
        return saved

    async def plant(self, hook_id: uuid.UUID, setup_chapter_id: uuid.UUID) -> Hook:
        hook = await self.get(hook_id)
        await self._require_chapter(hook.project_id, setup_chapter_id)
        if hook.status not in {HookStatus.PLANNED, HookStatus.PLANTED}:
            raise InvalidStateError("only planned/planted hooks can be planted")
        hook = hook.model_copy(update={"setup_chapter_id": setup_chapter_id, "status": HookStatus.PLANTED})
        saved = await self._uow.hooks.save(hook)
        await self._uow.commit()
        return saved

    async def activate(self, hook_id: uuid.UUID) -> Hook:
        hook = await self.get(hook_id)
        if hook.status is not HookStatus.PLANTED:
            raise InvalidStateError("hook must be planted before it can become active")
        hook = hook.model_copy(update={"status": HookStatus.ACTIVE})
        saved = await self._uow.hooks.save(hook)
        await self._uow.commit()
        return saved

    async def resolve(
        self,
        hook_id: uuid.UUID,
        resolved_chapter_id: uuid.UUID,
        *,
        confirmed_by: str,
    ) -> Hook:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required to resolve a hook")
        hook = await self.get(hook_id)
        await self._require_chapter(hook.project_id, resolved_chapter_id)
        if hook.status not in {HookStatus.PLANTED, HookStatus.ACTIVE}:
            raise InvalidStateError("only planted or active hooks can be resolved")
        hook = hook.model_copy(
            update={"resolved_chapter_id": resolved_chapter_id, "status": HookStatus.RESOLVED}
        )
        saved = await self._uow.hooks.save(hook)
        await self._uow.commit()
        return saved

    async def drop(self, hook_id: uuid.UUID, *, confirmed_by: str) -> Hook:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required to drop a hook")
        hook = await self.get(hook_id)
        hook = hook.model_copy(update={"status": HookStatus.DROPPED})
        saved = await self._uow.hooks.save(hook)
        await self._uow.commit()
        return saved

    async def _require_chapter(self, project_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
        chapter = await self._uow.chapters.get(chapter_id)
        if chapter is None or chapter.project_id != project_id:
            raise NotFoundError("chapter not found in this project")
