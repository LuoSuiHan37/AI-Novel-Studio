from __future__ import annotations

import uuid

from novel_engine.domain import approval
from novel_engine.domain.errors import DuplicateError, InvalidStateError, NotFoundError
from novel_engine.models.entities import StoryArc
from novel_engine.models.enums import ApprovalStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class StoryArcService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, arc_id: uuid.UUID) -> StoryArc:
        arc = await self._uow.story_arcs.get(arc_id)
        if arc is None:
            raise NotFoundError("story arc not found")
        return arc

    async def list(self, project_id: uuid.UUID) -> list[StoryArc]:
        await require_project(self._uow, project_id)
        return await self._uow.story_arcs.list_by_project(project_id)

    async def create(self, arc: StoryArc) -> StoryArc:
        await require_project(self._uow, arc.project_id)
        plot = await self._uow.master_plots.get(arc.master_plot_id)
        if plot is None or plot.project_id != arc.project_id:
            raise NotFoundError("master plot not found for this project")
        _validate_arc(arc)
        existing = await self._uow.story_arcs.list_by_project(arc.project_id)
        if any(item.sequence == arc.sequence for item in existing):
            raise DuplicateError(f"story arc sequence already used: {arc.sequence}")
        arc.status = ApprovalStatus.APPROVED
        saved = await self._uow.story_arcs.save(arc)
        await self._uow.commit()
        return saved

    async def update(self, arc: StoryArc) -> StoryArc:
        current = await self.get(arc.id)
        _validate_arc(arc)
        siblings = await self._uow.story_arcs.list_by_project(current.project_id)
        if any(item.sequence == arc.sequence and item.id != arc.id for item in siblings):
            raise DuplicateError(f"story arc sequence already used: {arc.sequence}")
        arc.status = ApprovalStatus.APPROVED
        saved = await self._uow.story_arcs.save(arc)
        await self._uow.commit()
        return saved

    async def submit_for_review(self, arc_id: uuid.UUID) -> StoryArc:
        arc = await self.get(arc_id)
        if arc.status is ApprovalStatus.APPROVED:
            return arc
        approval.submit_for_review(arc)
        saved = await self._uow.story_arcs.save(arc)
        await self._uow.commit()
        return saved

    async def approve(self, arc_id: uuid.UUID, *, confirmed_by: str) -> StoryArc:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        arc = await self.get(arc_id)
        if arc.status is ApprovalStatus.APPROVED:
            return arc
        approval.approve(arc)
        saved = await self._uow.story_arcs.save(arc)
        await self._uow.commit()
        return saved

    async def delete(self, arc_id: uuid.UUID) -> None:
        arc = await self.get(arc_id)
        if arc.status is ApprovalStatus.APPROVED:
            raise InvalidStateError("approved story arcs cannot be deleted")
        await self._uow.story_arcs.delete(arc_id)
        await self._uow.commit()


def _validate_arc(arc: StoryArc) -> None:
    if not arc.title.strip() or not arc.summary.strip():
        raise InvalidStateError("story arc title and summary are required")
    if arc.sequence < 1:
        raise InvalidStateError("story arc sequence must be >= 1")
    if (
        arc.start_chapter_number is not None
        and arc.end_chapter_number is not None
        and arc.end_chapter_number < arc.start_chapter_number
    ):
        raise InvalidStateError("end_chapter_number must be >= start_chapter_number")
