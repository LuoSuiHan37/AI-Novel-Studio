from __future__ import annotations

import uuid

from novel_engine.domain import approval
from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import Chapter, ChapterPlan, new_id
from novel_engine.models.enums import ApprovalStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class ChapterPlanService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, plan_id: uuid.UUID) -> ChapterPlan:
        plan = await self._uow.chapter_plans.get(plan_id)
        if plan is None:
            raise NotFoundError("chapter plan not found")
        return plan

    async def list(self, project_id: uuid.UUID) -> list[ChapterPlan]:
        await require_project(self._uow, project_id)
        return await self._uow.chapter_plans.list_by_project(project_id)

    async def create(self, plan: ChapterPlan) -> ChapterPlan:
        project = await require_project(self._uow, plan.project_id)
        _validate_plan(plan)
        target = project.chapter_count_target
        if target is not None and plan.chapter_number > target:
            raise InvalidStateError(
                f"chapter_number {plan.chapter_number} exceeds the book target of {target} chapters"
            )
        if plan.chapter_number > 1:
            previous = await self._uow.chapters.get_by_number(
                plan.project_id, plan.chapter_number - 1
            )
            if previous is None:
                raise InvalidStateError(
                    f"chapter {plan.chapter_number - 1} must be planned before chapter {plan.chapter_number}"
                )
        chapter = await self._ensure_chapter(plan)
        latest = await self._uow.chapter_plans.latest_for_chapter(chapter.id)
        version = 1 if latest is None else latest.version + 1
        plan = plan.model_copy(
            update={
                "chapter_id": chapter.id,
                "version": version,
                "status": ApprovalStatus.APPROVED,
            }
        )
        saved = await self._uow.chapter_plans.save(plan)
        chapter = await self._uow.chapters.get(chapter.id)
        if chapter is not None:
            metadata = dict(chapter.extra_metadata or {})
            metadata["slot"] = {
                "chapter_number": plan.chapter_number,
                "title": plan.chapter_title,
                "goal": plan.chapter_goal,
                "conflict": plan.conflict,
                "cliffhanger": plan.cliffhanger,
                "status": "planned",
            }
            await self._uow.chapters.save(chapter.model_copy(update={"extra_metadata": metadata}))
        await self._uow.commit()
        return saved

    async def update(self, plan: ChapterPlan) -> ChapterPlan:
        current = await self.get(plan.id)
        _validate_plan(plan)
        updated = plan.model_copy(
            update={
                "id": current.id,
                "chapter_id": current.chapter_id,
                "version": current.version,
                "project_id": current.project_id,
                "status": ApprovalStatus.APPROVED,
            }
        )
        saved = await self._uow.chapter_plans.save(updated)
        await self._uow.commit()
        return saved

    async def submit_for_review(self, plan_id: uuid.UUID) -> ChapterPlan:
        plan = await self.get(plan_id)
        if plan.status is ApprovalStatus.APPROVED:
            return plan
        scenes = await self._uow.scene_plans.list_by_plan(plan.id)
        if not scenes:
            raise InvalidStateError("add at least one scene plan before review")
        approval.submit_for_review(plan)
        saved = await self._uow.chapter_plans.save(plan)
        await self._uow.commit()
        return saved

    async def approve(self, plan_id: uuid.UUID, *, confirmed_by: str) -> ChapterPlan:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        plan = await self.get(plan_id)
        if plan.status is ApprovalStatus.APPROVED:
            return plan
        approval.approve(plan)
        saved = await self._uow.chapter_plans.save(plan)
        await self._uow.commit()
        return saved

    async def _fork_new_version(self, current: ChapterPlan, changes: ChapterPlan) -> ChapterPlan:
        _validate_plan(changes)
        next_plan = changes.model_copy(
            update={
                "id": new_id(),
                "project_id": current.project_id,
                "chapter_id": current.chapter_id,
                "chapter_number": current.chapter_number,
                "version": current.version + 1,
                "status": ApprovalStatus.APPROVED,
            }
        )
        saved = await self._uow.chapter_plans.save(next_plan)
        await self._uow.commit()
        return saved

    async def _ensure_chapter(self, plan: ChapterPlan) -> Chapter:
        existing = await self._uow.chapters.get_by_number(plan.project_id, plan.chapter_number)
        if existing is not None:
            if existing.title != plan.chapter_title:
                existing = existing.model_copy(update={"title": plan.chapter_title})
                await self._uow.chapters.save(existing)
            return existing
        chapter = Chapter(
            project_id=plan.project_id,
            chapter_number=plan.chapter_number,
            title=plan.chapter_title,
            content="",
        )
        await self._uow.chapters.save(chapter)
        return chapter


def _validate_plan(plan: ChapterPlan) -> None:
    required = {
        "chapter_title": plan.chapter_title,
        "pov": plan.pov,
        "location": plan.location,
        "chapter_goal": plan.chapter_goal,
        "conflict": plan.conflict,
        "emotional_arc": plan.emotional_arc,
        "new_information": plan.new_information,
        "reveal": plan.reveal,
        "foreshadowing": plan.foreshadowing,
        "setup": plan.setup,
        "payoff": plan.payoff,
        "cliffhanger": plan.cliffhanger,
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise InvalidStateError(f"chapter plan is missing fields: {', '.join(missing)}")
    if plan.chapter_number < 1:
        raise InvalidStateError("chapter_number must be >= 1")
    if not plan.characters:
        raise InvalidStateError("chapter plan needs at least one character")
