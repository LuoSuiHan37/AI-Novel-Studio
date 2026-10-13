from __future__ import annotations

from novel_engine.domain.errors import ApprovalRequiredError, InvalidStateError, NotFoundError
from novel_engine.models.entities import NovelProject, touch
from novel_engine.models.enums import ChapterStatus, PipelineStage, ProjectStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.style.chapter_repetition import scan_book_repetition
from novel_engine.style.chapter_relevance import scan_chapter_relevance

STAGE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.IDEA,
    PipelineStage.STORY_BIBLE,
    PipelineStage.WORLD_BIBLE,
    PipelineStage.CHARACTERS,
    PipelineStage.MASTER_PLOT,
    PipelineStage.CHAPTER_PLAN,
    PipelineStage.DRAFTING,
    PipelineStage.REVIEW,
    PipelineStage.PUBLISH,
)


class PipelineService:
    """Pipeline stage gate backed by automated readiness checks."""

    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def advance(self, project_id, *, confirmed_by: str) -> NovelProject:
        if not confirmed_by.strip():
            raise ApprovalRequiredError("confirmed_by is required to leave the current stage")
        project = await self._require_project(project_id)
        nxt = _next_stage(project.current_stage)
        await self._assert_ready(project, nxt)
        project.current_stage = nxt
        if nxt is PipelineStage.DRAFTING:
            project.status = ProjectStatus.WRITING
        touch(project)
        await self._uow.projects.save(project)
        await self._uow.commit()
        return project

    async def _assert_ready(self, project: NovelProject, target: PipelineStage) -> None:
        if target is PipelineStage.STORY_BIBLE:
            return
        if target is PipelineStage.WORLD_BIBLE:
            return
        if target is PipelineStage.CHARACTERS:
            world = await self._uow.world_bibles.get_by_project(project.id)
            if world is None:
                raise InvalidStateError("world bible is required before adding characters")
            return
        if target is PipelineStage.MASTER_PLOT:
            return
        if target is PipelineStage.CHAPTER_PLAN:
            return
        if target is PipelineStage.DRAFTING:
            return
        if target is PipelineStage.REVIEW:
            chapters = await self._uow.chapters.list_by_project(project.id)
            if not any(item.content.strip() for item in chapters):
                raise InvalidStateError("human-supplied chapter text is required before review")
            return
        if target is PipelineStage.PUBLISH:
            chapters = await self._uow.chapters.list_by_project(project.id)
            story = await self._uow.story_bibles.get_by_project(project.id)
            world = await self._uow.world_bibles.get_by_project(project.id)
            characters = await self._uow.characters.list_by_project(project.id)
            plots = await self._uow.master_plots.list_by_project(project.id)
            arcs = await self._uow.story_arcs.list_by_project(project.id)
            active_plot = next((item for item in plots if item.is_active), plots[0] if plots else None)
            if story is None or world is None or not characters or active_plot is None or not arcs:
                raise InvalidStateError("cannot publish: complete story bible, world bible, characters, master plot, and arcs are required")
            if len(active_plot.beats) < 3:
                raise InvalidStateError("cannot publish: master plot needs at least three beats")
            target_count = project.chapter_count_target
            if target_count is not None:
                uncovered = [
                    number for number in range(1, target_count + 1)
                    if not any(
                        (arc.start_chapter_number or 1) <= number <= (arc.end_chapter_number or target_count)
                        for arc in arcs
                    )
                ]
                if uncovered:
                    raise InvalidStateError(
                        f"cannot publish: story arcs do not cover chapter {uncovered[0]}"
                    )
            chapter_numbers = {item.chapter_number for item in chapters}
            if target_count:
                missing = [number for number in range(1, target_count + 1) if number not in chapter_numbers]
                if missing:
                    preview = ", ".join(str(item) for item in missing[:12])
                    suffix = "..." if len(missing) > 12 else ""
                    raise InvalidStateError(f"cannot publish: missing planned chapters {preview}{suffix}")
                overflow = sorted(number for number in chapter_numbers if number > target_count)
                if overflow:
                    raise InvalidStateError(f"cannot publish: chapter {overflow[0]} exceeds planned total {target_count}")
            empty = next((item.chapter_number for item in chapters if not item.content.strip()), None)
            if empty is not None:
                raise InvalidStateError(f"cannot publish: chapter {empty} is empty")
            unfinished = next(
                (item.chapter_number for item in chapters
                 if item.status not in {ChapterStatus.APPROVED, ChapterStatus.PUBLISHED}),
                None,
            )
            if unfinished is not None:
                raise InvalidStateError(f"cannot publish: chapter {unfinished} has not passed review and approval")
            findings = scan_book_repetition(chapters)
            if findings:
                first = findings[0]
                raise InvalidStateError(
                    f"cannot publish: chapter {first['chapter_number']} duplicates "
                    f"chapter {first['matched_chapter_number']} ({first['reason']})"
                )
            for chapter in chapters:
                plan = await self._uow.chapter_plans.latest_for_chapter(chapter.id)
                if plan is None:
                    raise InvalidStateError(f"cannot publish: chapter {chapter.chapter_number} has no chapter plan")
                scenes = await self._uow.scene_plans.list_by_plan(plan.id)
                relevance = scan_chapter_relevance(content=chapter.content, plan=plan, scenes=scenes)
                if relevance.blocked:
                    raise InvalidStateError(
                        f"cannot publish: chapter {chapter.chapter_number} is unrelated to its chapter plan"
                    )
            return

    async def _require_project(self, project_id) -> NovelProject:
        project = await self._uow.projects.get(project_id)
        if project is None:
            raise NotFoundError("project not found")
        return project


def _next_stage(current: PipelineStage) -> PipelineStage:
    try:
        index = STAGE_ORDER.index(current)
    except ValueError as exc:
        raise InvalidStateError(f"unknown stage: {current}") from exc
    if index >= len(STAGE_ORDER) - 1:
        raise InvalidStateError("project is already at the final stage")
    return STAGE_ORDER[index + 1]
