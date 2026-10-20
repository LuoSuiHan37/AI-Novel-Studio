from uuid import uuid4

import pytest

from novel_engine.models.entities import Chapter, ChapterPlan, NovelProject, ScenePlan
from novel_engine.models.enums import ApprovalStatus, ChapterStatus
from novel_engine.domain.errors import DuplicateError
from novel_engine.ports.in_memory import InMemoryUnitOfWork
from novel_engine.services.novel_audit import audit_novel_for_publish


def _scene(plan_id, number=1, *, complete=True):
    values = {
        "protagonist_want": "拿到账册",
        "active_pressure": "守卫正在搜查",
        "choice_and_cost": "她烧掉证据，失去唯一退路",
        "irreversible_change": "账册只剩一页，盟友不再信任她",
    }
    if not complete:
        values["choice_and_cost"] = ""
    return ScenePlan(
        chapter_plan_id=plan_id,
        scene_number=number,
        location="后院",
        characters=["林岚"],
        goal="拿到账册",
        conflict="守卫搜查",
        turning_point="她决定烧掉证据",
        dialogue_goal="逼问账房",
        emotion="紧绷",
        information_revealed="账册被调包",
        ending="她只留下半页",
        **values,
    )


@pytest.mark.asyncio
async def test_publish_audit_does_not_hide_duplicate_numbers_and_requires_scene_contract():
    uow = InMemoryUnitOfWork()
    project = NovelProject(title="audit", chapter_count_target=1)
    await uow.projects.add(project)
    chapter = Chapter(
        project_id=project.id,
        chapter_number=1,
        title="夜查",
        content="她走进后院，发现账册被调包。" * 30,
        status=ChapterStatus.APPROVED,
    )
    await uow.chapters.save(chapter)
    plan = ChapterPlan(
        project_id=project.id,
        chapter_id=chapter.id,
        chapter_number=1,
        chapter_title="夜查",
        pov="林岚",
        location="后院",
        characters=["林岚"],
        chapter_goal="拿到账册",
        conflict="守卫搜查",
        emotional_arc="怀疑到决断",
        new_information="账册被调包",
        reveal="有人提前动过账",
        foreshadowing="半枚印章",
        setup="账房封门",
        payoff="她烧掉证据",
        cliffhanger="半页账纸落入水中",
        status=ApprovalStatus.APPROVED,
    )
    await uow.chapter_plans.save(plan)
    await uow.scene_plans.save(_scene(plan.id, complete=False))
    report = await audit_novel_for_publish(uow, project)
    assert not report.passed
    assert "scene_agency_contract_missing" in {item.code for item in report.findings}


@pytest.mark.asyncio
async def test_in_memory_chapters_reject_same_number():
    uow = InMemoryUnitOfWork()
    project_id = uuid4()
    await uow.chapters.save(Chapter(project_id=project_id, chapter_number=1, title="a"))
    with pytest.raises(DuplicateError):
        await uow.chapters.save(Chapter(project_id=project_id, chapter_number=1, title="b"))
