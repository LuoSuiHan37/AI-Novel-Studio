from __future__ import annotations

import uuid

from novel_engine.domain.errors import DuplicateError, InvalidStateError, NotFoundError
from novel_engine.models.entities import ScenePlan
from novel_engine.models.enums import ApprovalStatus
from novel_engine.ports.repositories import NovelUnitOfWork


class ScenePlanService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, scene_id: uuid.UUID) -> ScenePlan:
        scene = await self._uow.scene_plans.get(scene_id)
        if scene is None:
            raise NotFoundError("scene plan not found")
        return scene

    async def list(self, chapter_plan_id: uuid.UUID) -> list[ScenePlan]:
        await self._require_plan(chapter_plan_id)
        return await self._uow.scene_plans.list_by_plan(chapter_plan_id)

    async def create(self, scene: ScenePlan, *, commit: bool = True) -> ScenePlan:
        plan = await self._require_plan(scene.chapter_plan_id)
        _validate_scene(scene)
        existing = await self._uow.scene_plans.list_by_plan(scene.chapter_plan_id)
        if any(item.scene_number == scene.scene_number for item in existing):
            raise DuplicateError(f"scene_number already used: {scene.scene_number}")
        saved = await self._uow.scene_plans.save(scene)
        if commit:
            await self._uow.commit()
        return saved

    async def update(self, scene: ScenePlan) -> ScenePlan:
        current = await self.get(scene.id)
        plan = await self._require_plan(current.chapter_plan_id)
        _validate_scene(scene)
        scene = scene.model_copy(update={"chapter_plan_id": current.chapter_plan_id, "id": current.id})
        saved = await self._uow.scene_plans.save(scene)
        await self._uow.commit()
        return saved

    async def delete(self, scene_id: uuid.UUID) -> None:
        scene = await self.get(scene_id)
        plan = await self._require_plan(scene.chapter_plan_id)
        if plan.status is ApprovalStatus.APPROVED:
            raise InvalidStateError("cannot delete scenes on an approved chapter plan")
        await self._uow.scene_plans.delete(scene_id)
        await self._uow.commit()

    async def _require_plan(self, chapter_plan_id: uuid.UUID):
        plan = await self._uow.chapter_plans.get(chapter_plan_id)
        if plan is None:
            raise NotFoundError("chapter plan not found")
        return plan


def _validate_scene(scene: ScenePlan) -> None:
    required = {
        "location": scene.location,
        "goal": scene.goal,
        "conflict": scene.conflict,
        "turning_point": scene.turning_point,
        "dialogue_goal": scene.dialogue_goal,
        "emotion": scene.emotion,
        "information_revealed": scene.information_revealed,
        "ending": scene.ending,
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise InvalidStateError(f"scene plan is missing fields: {', '.join(missing)}")
    if scene.scene_number < 1:
        raise InvalidStateError("scene_number must be >= 1")
    if not scene.characters:
        raise InvalidStateError("scene plan needs at least one character")
