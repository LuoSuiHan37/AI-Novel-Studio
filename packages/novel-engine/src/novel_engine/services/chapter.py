from __future__ import annotations

import uuid

from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import Chapter
from novel_engine.models.enums import ChapterStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class ChapterService:
    """Chapter row lifecycle. Prose snapshots go through RevisionService."""

    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def list(self, project_id: uuid.UUID) -> list[Chapter]:
        await require_project(self._uow, project_id)
        return await self._uow.chapters.list_by_project(project_id)

    async def get_by_number(self, project_id: uuid.UUID, chapter_number: int) -> Chapter:
        await require_project(self._uow, project_id)
        chapter = await self._uow.chapters.get_by_number(project_id, chapter_number)
        if chapter is None:
            raise NotFoundError("chapter not found")
        return chapter

    async def update(self, chapter: Chapter, *, commit: bool = True) -> Chapter:
        current = await self._uow.chapters.get(chapter.id)
        if current is None:
            raise NotFoundError("chapter not found")
        if current.project_id != chapter.project_id:
            raise InvalidStateError("cannot move a chapter to another project")
        saved = await self._uow.chapters.save(
            current.model_copy(
                update={
                    "title": chapter.title or current.title,
                    "story_arc_id": chapter.story_arc_id,
                    # Preserve the caller's lifecycle transition when the
                    # chapter is updated together with audit metadata. Most
                    # callers pass the freshly loaded status; silently
                    # forcing the old status can undo a successful review.
                    "status": chapter.status,
                    "content": current.content,
                    "word_count": current.word_count,
                    "current_revision_id": current.current_revision_id,
                    "extra_metadata": dict(chapter.extra_metadata or current.extra_metadata or {}),
                }
            )
        )
        if commit:
            await self._uow.commit()
        return saved

    async def mark_reviewed(self, project_id: uuid.UUID, chapter_number: int) -> Chapter:
        chapter = await self.get_by_number(project_id, chapter_number)
        if not chapter.content.strip():
            raise InvalidStateError("cannot review an empty chapter")
        saved = await self._uow.chapters.save(chapter.model_copy(update={"status": ChapterStatus.REVIEWED}))
        await self._uow.commit()
        return saved

    async def approve(
        self,
        project_id: uuid.UUID,
        chapter_number: int,
        *,
        confirmed_by: str,
        commit: bool = True,
    ) -> Chapter:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        chapter = await self.get_by_number(project_id, chapter_number)
        if not chapter.content.strip():
            raise InvalidStateError("cannot approve an empty chapter")
        if chapter.status is ChapterStatus.DRAFT:
            raise InvalidStateError("review the chapter before approving")
        saved = await self._uow.chapters.save(chapter.model_copy(update={"status": ChapterStatus.APPROVED}))
        if commit:
            await self._uow.commit()
        return saved
