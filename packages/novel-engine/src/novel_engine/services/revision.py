from __future__ import annotations

import uuid

from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import Chapter, ChapterRevision, new_id
from novel_engine.models.enums import ChapterStatus
from novel_engine.style.word_count import count_text_units
from novel_engine.ports.repositories import NovelUnitOfWork


class RevisionService:
    """Version snapshots for human-supplied chapter text. Does not generate prose."""

    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def list(self, chapter_id: uuid.UUID) -> list[ChapterRevision]:
        await self._require_chapter(chapter_id)
        return await self._uow.revisions.list_by_chapter(chapter_id)

    async def save_snapshot(
        self,
        chapter_id: uuid.UUID,
        content: str,
        *,
        created_by: str = "human",
        change_summary: str | None = None,
    ) -> ChapterRevision:
        chapter = await self._require_chapter(chapter_id)
        text = content.strip()
        if not text:
            raise InvalidStateError("cannot snapshot empty chapter text")
        await self._ensure_platform_length(chapter.project_id, text)
        existing = await self._uow.revisions.list_by_chapter(chapter_id)
        revision = ChapterRevision(
            chapter_id=chapter_id,
            revision_number=(existing[-1].revision_number + 1) if existing else 1,
            content=text,
            word_count=count_text_units(text),
            change_summary=change_summary,
            created_by=created_by or "human",
        )
        saved = await self._uow.revisions.save(revision)
        chapter = chapter.model_copy(
            update={
                "content": saved.content,
                "word_count": saved.word_count,
                "current_revision_id": saved.id,
                "status": ChapterStatus.DRAFT,
                "extra_metadata": {
                    key: value
                    for key, value in chapter.extra_metadata.items()
                    if key != "audit"
                },
            }
        )
        await self._uow.chapters.save(chapter)
        await self._uow.commit()
        return saved

    async def restore(
        self,
        chapter_id: uuid.UUID,
        revision_id: uuid.UUID,
        *,
        confirmed_by: str,
    ) -> ChapterRevision:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required to restore a revision")
        chapter = await self._require_chapter(chapter_id)
        source = await self._uow.revisions.get(revision_id)
        if source is None or source.chapter_id != chapter_id:
            raise NotFoundError("revision not found for this chapter")
        existing = await self._uow.revisions.list_by_chapter(chapter_id)
        restored = ChapterRevision(
            id=new_id(),
            chapter_id=chapter_id,
            revision_number=existing[-1].revision_number + 1,
            content=source.content,
            word_count=source.word_count,
            change_summary=f"Restored from revision {source.revision_number}",
            restored_from_revision_id=source.id,
            created_by=confirmed_by,
        )
        await self._ensure_platform_length(chapter.project_id, restored.content)
        saved = await self._uow.revisions.save(restored)
        chapter = chapter.model_copy(
            update={
                "content": saved.content,
                "word_count": saved.word_count,
                "current_revision_id": saved.id,
                "status": ChapterStatus.DRAFT,
                "extra_metadata": {
                    key: value
                    for key, value in chapter.extra_metadata.items()
                    if key != "audit"
                },
            }
        )
        await self._uow.chapters.save(chapter)
        await self._uow.commit()
        return saved

    async def _require_chapter(self, chapter_id: uuid.UUID) -> Chapter:
        chapter = await self._uow.chapters.get(chapter_id)
        if chapter is None:
            raise NotFoundError("chapter not found")
        return chapter

    async def _ensure_platform_length(self, project_id: uuid.UUID, text: str) -> None:
        """Keep length validation advisory so drafts are never lost.

        The generation pipeline reports the measured count and target range to
        the caller. Persistence must not repeat the old hard rejection here:
        an out-of-range draft is still recoverable and can be corrected in the
        editor. Empty text remains rejected by ``save_snapshot`` itself.
        """
        return
