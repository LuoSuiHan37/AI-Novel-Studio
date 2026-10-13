from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters import mapping
from app.db.models.bible import StoryBible as StoryBibleRow
from app.db.models.bible import WorldBible as WorldBibleRow
from app.db.models.bible import WorldRule as WorldRuleRow
from app.db.models.chapter import Chapter as ChapterRow
from app.db.models.chapter import ChapterPlan as ChapterPlanRow
from app.db.models.chapter import ChapterRevision as ChapterRevisionRow
from app.db.models.chapter import ScenePlan as ScenePlanRow
from app.db.models.character import Character as CharacterRow
from app.db.models.continuity import Foreshadowing as ForeshadowingRow
from app.db.models.continuity import Hook as HookRow
from app.db.models.plot import MasterPlot as MasterPlotRow
from app.db.models.plot import StoryArc as StoryArcRow
from app.db.models.project import NovelProject as ProjectRow
from novel_engine.models.entities import (
    Chapter,
    ChapterPlan,
    ChapterRevision,
    Character,
    Foreshadowing,
    Hook,
    MasterPlot,
    NovelProject,
    ScenePlan,
    StoryArc,
    StoryBible,
    WorldBible,
)
from novel_engine.ports.repositories import NovelUnitOfWork


async def _flush_refresh(session: AsyncSession, row):
    await session.flush()
    await session.refresh(row)
    return row


class SqlAlchemyUnitOfWork(NovelUnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = _ProjectRepo(session)
        self.story_bibles = _StoryBibleRepo(session)
        self.world_bibles = _WorldBibleRepo(session)
        self.characters = _CharacterRepo(session)
        self.master_plots = _MasterPlotRepo(session)
        self.story_arcs = _StoryArcRepo(session)
        self.chapters = _ChapterRepo(session)
        self.chapter_plans = _ChapterPlanRepo(session)
        self.scene_plans = _ScenePlanRepo(session)
        self.revisions = _RevisionRepo(session)
        self.hooks = _HookRepo(session)
        self.foreshadowings = _ForeshadowRepo(session)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class _ProjectRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, project_id: uuid.UUID) -> NovelProject | None:
        row = await self._session.get(ProjectRow, project_id)
        return mapping.project_to_domain(row) if row else None

    async def list(self) -> list[NovelProject]:
        result = await self._session.scalars(select(ProjectRow).order_by(ProjectRow.created_at.desc()))
        return [mapping.project_to_domain(row) for row in result.all()]

    async def add(self, project: NovelProject) -> NovelProject:
        row = ProjectRow(id=project.id)
        mapping.apply_project(row, project)
        self._session.add(row)
        await _flush_refresh(self._session, row)
        return mapping.project_to_domain(row)

    async def save(self, project: NovelProject) -> NovelProject:
        row = await self._session.get(ProjectRow, project.id)
        if row is None:
            return await self.add(project)
        mapping.apply_project(row, project)
        await _flush_refresh(self._session, row)
        return mapping.project_to_domain(row)

    async def delete(self, project_id: uuid.UUID) -> None:
        row = await self._session.get(ProjectRow, project_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()


class _StoryBibleRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_project(self, project_id: uuid.UUID) -> StoryBible | None:
        row = await self._session.scalar(select(StoryBibleRow).where(StoryBibleRow.project_id == project_id))
        return mapping.story_bible_to_domain(row) if row else None

    async def save(self, bible: StoryBible) -> StoryBible:
        row = await self._session.get(StoryBibleRow, bible.id)
        if row is None:
            existing = await self._session.scalar(
                select(StoryBibleRow).where(StoryBibleRow.project_id == bible.project_id)
            )
            row = existing
        if row is None:
            row = StoryBibleRow(id=bible.id, project_id=bible.project_id)
            self._session.add(row)
        mapping.apply_story_bible(row, bible)
        await _flush_refresh(self._session, row)
        return mapping.story_bible_to_domain(row)


class _WorldBibleRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load(self, project_id: uuid.UUID) -> WorldBibleRow | None:
        return await self._session.scalar(
            select(WorldBibleRow)
            .options(selectinload(WorldBibleRow.rules))
            .where(WorldBibleRow.project_id == project_id)
        )

    async def get_by_project(self, project_id: uuid.UUID) -> WorldBible | None:
        row = await self._load(project_id)
        return mapping.world_bible_to_domain(row) if row else None

    async def save(self, bible: WorldBible) -> WorldBible:
        row = await self._session.get(WorldBibleRow, bible.id)
        if row is None:
            row = await self._load(bible.project_id)
        if row is None:
            row = WorldBibleRow(id=bible.id, project_id=bible.project_id)
            mapping.apply_world_bible(row, bible)
            self._session.add(row)
        else:
            mapping.apply_world_bible(row, bible)
        await self._session.flush()
        existing_rows = (
            await self._session.scalars(select(WorldRuleRow).where(WorldRuleRow.world_bible_id == row.id))
        ).all()
        existing = {item.id: item for item in existing_rows}
        keep: set[uuid.UUID] = set()
        for rule in bible.rules:
            current = existing.get(rule.id)
            if current is None:
                current = WorldRuleRow(
                    id=rule.id,
                    world_bible_id=row.id,
                    name=rule.name,
                    category=rule.category,
                    description=rule.description,
                    is_hard_constraint=rule.is_hard_constraint,
                )
                self._session.add(current)
            else:
                current.name = rule.name
                current.category = rule.category
                current.description = rule.description
                current.is_hard_constraint = rule.is_hard_constraint
            keep.add(current.id)
        for item in existing_rows:
            if item.id not in keep:
                await self._session.delete(item)
        await self._session.flush()
        reloaded = await self._load(bible.project_id)
        return mapping.world_bible_to_domain(reloaded or row)


class _CharacterRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, character_id: uuid.UUID) -> Character | None:
        row = await self._session.get(CharacterRow, character_id)
        return mapping.character_to_domain(row) if row else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Character]:
        result = await self._session.scalars(
            select(CharacterRow).where(CharacterRow.project_id == project_id).order_by(CharacterRow.name)
        )
        return [mapping.character_to_domain(row) for row in result.all()]

    async def save(self, character: Character) -> Character:
        row = await self._session.get(CharacterRow, character.id)
        if row is None:
            row = CharacterRow(id=character.id, project_id=character.project_id)
            self._session.add(row)
        mapping.apply_character(row, character)
        await _flush_refresh(self._session, row)
        return mapping.character_to_domain(row)

    async def delete(self, character_id: uuid.UUID) -> None:
        row = await self._session.get(CharacterRow, character_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()


class _MasterPlotRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, plot_id: uuid.UUID) -> MasterPlot | None:
        row = await self._session.get(MasterPlotRow, plot_id)
        return mapping.plot_to_domain(row) if row else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[MasterPlot]:
        result = await self._session.scalars(
            select(MasterPlotRow).where(MasterPlotRow.project_id == project_id)
        )
        return [mapping.plot_to_domain(row) for row in result.all()]

    async def save(self, plot: MasterPlot) -> MasterPlot:
        row = await self._session.get(MasterPlotRow, plot.id)
        if row is None:
            row = MasterPlotRow(id=plot.id, project_id=plot.project_id)
            self._session.add(row)
        mapping.apply_plot(row, plot)
        await _flush_refresh(self._session, row)
        return mapping.plot_to_domain(row)


class _StoryArcRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, arc_id: uuid.UUID) -> StoryArc | None:
        row = await self._session.get(StoryArcRow, arc_id)
        return mapping.arc_to_domain(row) if row else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[StoryArc]:
        result = await self._session.scalars(
            select(StoryArcRow).where(StoryArcRow.project_id == project_id).order_by(StoryArcRow.sequence)
        )
        return [mapping.arc_to_domain(row) for row in result.all() if row.master_plot_id is not None]

    async def list_by_plot(self, plot_id: uuid.UUID) -> list[StoryArc]:
        result = await self._session.scalars(
            select(StoryArcRow).where(StoryArcRow.master_plot_id == plot_id)
        )
        return [mapping.arc_to_domain(row) for row in result.all() if row.master_plot_id is not None]

    async def save(self, arc: StoryArc) -> StoryArc:
        row = await self._session.get(StoryArcRow, arc.id)
        if row is None:
            row = StoryArcRow(id=arc.id, project_id=arc.project_id)
            self._session.add(row)
        mapping.apply_arc(row, arc)
        await _flush_refresh(self._session, row)
        return mapping.arc_to_domain(row)

    async def delete(self, arc_id: uuid.UUID) -> None:
        row = await self._session.get(StoryArcRow, arc_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()


class _ChapterRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, chapter_id: uuid.UUID) -> Chapter | None:
        row = await self._session.get(ChapterRow, chapter_id)
        return mapping.chapter_to_domain(row) if row else None

    async def get_by_number(self, project_id: uuid.UUID, chapter_number: int) -> Chapter | None:
        row = await self._session.scalar(
            select(ChapterRow).where(
                ChapterRow.project_id == project_id,
                ChapterRow.chapter_number == chapter_number,
            )
        )
        return mapping.chapter_to_domain(row) if row else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Chapter]:
        result = await self._session.scalars(
            select(ChapterRow)
            .where(ChapterRow.project_id == project_id)
            .order_by(ChapterRow.chapter_number)
        )
        return [mapping.chapter_to_domain(row) for row in result.all()]

    async def save(self, chapter: Chapter) -> Chapter:
        row = await self._session.get(ChapterRow, chapter.id)
        if row is None:
            row = ChapterRow(id=chapter.id, project_id=chapter.project_id)
            self._session.add(row)
        mapping.apply_chapter(row, chapter)
        await _flush_refresh(self._session, row)
        return mapping.chapter_to_domain(row)


class _ChapterPlanRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, plan_id: uuid.UUID) -> ChapterPlan | None:
        row = await self._session.get(ChapterPlanRow, plan_id)
        return mapping.plan_to_domain(row) if row else None

    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[ChapterPlan]:
        result = await self._session.scalars(
            select(ChapterPlanRow)
            .where(ChapterPlanRow.chapter_id == chapter_id)
            .order_by(ChapterPlanRow.version)
        )
        return [mapping.plan_to_domain(row) for row in result.all()]

    async def list_by_project(self, project_id: uuid.UUID) -> list[ChapterPlan]:
        result = await self._session.scalars(
            select(ChapterPlanRow).where(ChapterPlanRow.project_id == project_id)
        )
        return [mapping.plan_to_domain(row) for row in result.all()]

    async def latest_for_chapter(self, chapter_id: uuid.UUID) -> ChapterPlan | None:
        items = await self.list_by_chapter(chapter_id)
        return items[-1] if items else None

    async def save(self, plan: ChapterPlan) -> ChapterPlan:
        row = await self._session.get(ChapterPlanRow, plan.id)
        if row is None:
            row = ChapterPlanRow(id=plan.id, project_id=plan.project_id, chapter_id=plan.chapter_id)
            self._session.add(row)
        mapping.apply_plan(row, plan)
        await _flush_refresh(self._session, row)
        return mapping.plan_to_domain(row)


class _ScenePlanRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, scene_id: uuid.UUID) -> ScenePlan | None:
        row = await self._session.get(ScenePlanRow, scene_id)
        return mapping.scene_to_domain(row) if row else None

    async def list_by_plan(self, chapter_plan_id: uuid.UUID) -> list[ScenePlan]:
        result = await self._session.scalars(
            select(ScenePlanRow)
            .where(ScenePlanRow.chapter_plan_id == chapter_plan_id)
            .order_by(ScenePlanRow.scene_number)
        )
        return [mapping.scene_to_domain(row) for row in result.all()]

    async def save(self, scene: ScenePlan) -> ScenePlan:
        row = await self._session.get(ScenePlanRow, scene.id)
        if row is None:
            row = ScenePlanRow(id=scene.id, chapter_plan_id=scene.chapter_plan_id)
            self._session.add(row)
        mapping.apply_scene(row, scene)
        await _flush_refresh(self._session, row)
        return mapping.scene_to_domain(row)

    async def delete(self, scene_id: uuid.UUID) -> None:
        row = await self._session.get(ScenePlanRow, scene_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()


class _RevisionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, revision_id: uuid.UUID) -> ChapterRevision | None:
        row = await self._session.get(ChapterRevisionRow, revision_id)
        return mapping.revision_to_domain(row) if row else None

    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[ChapterRevision]:
        result = await self._session.scalars(
            select(ChapterRevisionRow)
            .where(ChapterRevisionRow.chapter_id == chapter_id)
            .order_by(ChapterRevisionRow.revision_number)
        )
        return [mapping.revision_to_domain(row) for row in result.all()]

    async def save(self, revision: ChapterRevision) -> ChapterRevision:
        row = await self._session.get(ChapterRevisionRow, revision.id)
        if row is None:
            row = ChapterRevisionRow(id=revision.id, chapter_id=revision.chapter_id)
            self._session.add(row)
        mapping.apply_revision(row, revision)
        await _flush_refresh(self._session, row)
        return mapping.revision_to_domain(row)


class _HookRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, hook_id: uuid.UUID) -> Hook | None:
        row = await self._session.get(HookRow, hook_id)
        return mapping.hook_to_domain(row) if row else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Hook]:
        result = await self._session.scalars(select(HookRow).where(HookRow.project_id == project_id))
        return [mapping.hook_to_domain(row) for row in result.all()]

    async def save(self, hook: Hook) -> Hook:
        row = await self._session.get(HookRow, hook.id)
        if row is None:
            row = HookRow(id=hook.id, project_id=hook.project_id)
            self._session.add(row)
        mapping.apply_hook(row, hook)
        await _flush_refresh(self._session, row)
        return mapping.hook_to_domain(row)


class _ForeshadowRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, item_id: uuid.UUID) -> Foreshadowing | None:
        row = await self._session.get(ForeshadowingRow, item_id)
        return mapping.foreshadow_to_domain(row) if row else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Foreshadowing]:
        result = await self._session.scalars(
            select(ForeshadowingRow).where(ForeshadowingRow.project_id == project_id)
        )
        return [mapping.foreshadow_to_domain(row) for row in result.all()]

    async def save(self, item: Foreshadowing) -> Foreshadowing:
        row = await self._session.get(ForeshadowingRow, item.id)
        if row is None:
            row = ForeshadowingRow(id=item.id, project_id=item.project_id)
            self._session.add(row)
        mapping.apply_foreshadow(row, item)
        await _flush_refresh(self._session, row)
        return mapping.foreshadow_to_domain(row)
