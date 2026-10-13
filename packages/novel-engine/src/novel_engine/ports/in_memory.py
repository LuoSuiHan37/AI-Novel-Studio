from __future__ import annotations

import uuid

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


class InMemoryUnitOfWork(NovelUnitOfWork):
    """Test double. Production persistence belongs in apps/api adapters."""

    def __init__(self) -> None:
        self.projects = _ProjectRepo()
        self.story_bibles = _StoryBibleRepo()
        self.world_bibles = _WorldBibleRepo()
        self.characters = _CharacterRepo()
        self.master_plots = _MasterPlotRepo()
        self.story_arcs = _StoryArcRepo()
        self.chapters = _ChapterRepo()
        self.chapter_plans = _ChapterPlanRepo()
        self.scene_plans = _ScenePlanRepo()
        self.revisions = _RevisionRepo()
        self.hooks = _HookRepo()
        self.foreshadowings = _ForeshadowRepo()

    async def commit(self) -> None:
        return None


class _ProjectRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, NovelProject] = {}

    async def get(self, project_id: uuid.UUID) -> NovelProject | None:
        item = self._items.get(project_id)
        return item.model_copy(deep=True) if item else None

    async def add(self, project: NovelProject) -> NovelProject:
        self._items[project.id] = project.model_copy(deep=True)
        return project

    async def save(self, project: NovelProject) -> NovelProject:
        return await self.add(project)

    async def list(self) -> list[NovelProject]:
        return [item.model_copy(deep=True) for item in self._items.values()]

    async def delete(self, project_id: uuid.UUID) -> None:
        self._items.pop(project_id, None)


class _StoryBibleRepo:
    def __init__(self) -> None:
        self._by_project: dict[uuid.UUID, StoryBible] = {}

    async def get_by_project(self, project_id: uuid.UUID) -> StoryBible | None:
        item = self._by_project.get(project_id)
        return item.model_copy(deep=True) if item else None

    async def save(self, bible: StoryBible) -> StoryBible:
        self._by_project[bible.project_id] = bible.model_copy(deep=True)
        return bible


class _WorldBibleRepo:
    def __init__(self) -> None:
        self._by_project: dict[uuid.UUID, WorldBible] = {}

    async def get_by_project(self, project_id: uuid.UUID) -> WorldBible | None:
        item = self._by_project.get(project_id)
        return item.model_copy(deep=True) if item else None

    async def save(self, bible: WorldBible) -> WorldBible:
        self._by_project[bible.project_id] = bible.model_copy(deep=True)
        return bible


class _CharacterRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, Character] = {}

    async def get(self, character_id: uuid.UUID) -> Character | None:
        item = self._items.get(character_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Character]:
        return [item.model_copy(deep=True) for item in self._items.values() if item.project_id == project_id]

    async def save(self, character: Character) -> Character:
        self._items[character.id] = character.model_copy(deep=True)
        return character

    async def delete(self, character_id: uuid.UUID) -> None:
        self._items.pop(character_id, None)


class _MasterPlotRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, MasterPlot] = {}

    async def get(self, plot_id: uuid.UUID) -> MasterPlot | None:
        item = self._items.get(plot_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[MasterPlot]:
        return [item.model_copy(deep=True) for item in self._items.values() if item.project_id == project_id]

    async def save(self, plot: MasterPlot) -> MasterPlot:
        self._items[plot.id] = plot.model_copy(deep=True)
        return plot


class _StoryArcRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, StoryArc] = {}

    async def get(self, arc_id: uuid.UUID) -> StoryArc | None:
        item = self._items.get(arc_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[StoryArc]:
        return sorted(
            [item.model_copy(deep=True) for item in self._items.values() if item.project_id == project_id],
            key=lambda item: item.sequence,
        )

    async def list_by_plot(self, plot_id: uuid.UUID) -> list[StoryArc]:
        return [item.model_copy(deep=True) for item in self._items.values() if item.master_plot_id == plot_id]

    async def save(self, arc: StoryArc) -> StoryArc:
        self._items[arc.id] = arc.model_copy(deep=True)
        return arc

    async def delete(self, arc_id: uuid.UUID) -> None:
        self._items.pop(arc_id, None)


class _ChapterRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, Chapter] = {}

    async def get(self, chapter_id: uuid.UUID) -> Chapter | None:
        item = self._items.get(chapter_id)
        return item.model_copy(deep=True) if item else None

    async def get_by_number(self, project_id: uuid.UUID, chapter_number: int) -> Chapter | None:
        for item in self._items.values():
            if item.project_id == project_id and item.chapter_number == chapter_number:
                return item.model_copy(deep=True)
        return None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Chapter]:
        return sorted(
            [item.model_copy(deep=True) for item in self._items.values() if item.project_id == project_id],
            key=lambda item: item.chapter_number,
        )

    async def save(self, chapter: Chapter) -> Chapter:
        self._items[chapter.id] = chapter.model_copy(deep=True)
        return chapter


class _ChapterPlanRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, ChapterPlan] = {}

    async def get(self, plan_id: uuid.UUID) -> ChapterPlan | None:
        item = self._items.get(plan_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[ChapterPlan]:
        return sorted(
            [item.model_copy(deep=True) for item in self._items.values() if item.chapter_id == chapter_id],
            key=lambda item: item.version,
        )

    async def list_by_project(self, project_id: uuid.UUID) -> list[ChapterPlan]:
        return [item.model_copy(deep=True) for item in self._items.values() if item.project_id == project_id]

    async def latest_for_chapter(self, chapter_id: uuid.UUID) -> ChapterPlan | None:
        items = await self.list_by_chapter(chapter_id)
        return items[-1] if items else None

    async def save(self, plan: ChapterPlan) -> ChapterPlan:
        self._items[plan.id] = plan.model_copy(deep=True)
        return plan


class _ScenePlanRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, ScenePlan] = {}

    async def get(self, scene_id: uuid.UUID) -> ScenePlan | None:
        item = self._items.get(scene_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_plan(self, chapter_plan_id: uuid.UUID) -> list[ScenePlan]:
        return sorted(
            [item.model_copy(deep=True) for item in self._items.values() if item.chapter_plan_id == chapter_plan_id],
            key=lambda item: item.scene_number,
        )

    async def save(self, scene: ScenePlan) -> ScenePlan:
        self._items[scene.id] = scene.model_copy(deep=True)
        return scene

    async def delete(self, scene_id: uuid.UUID) -> None:
        self._items.pop(scene_id, None)


class _RevisionRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, ChapterRevision] = {}

    async def get(self, revision_id: uuid.UUID) -> ChapterRevision | None:
        item = self._items.get(revision_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[ChapterRevision]:
        return sorted(
            [item.model_copy(deep=True) for item in self._items.values() if item.chapter_id == chapter_id],
            key=lambda item: item.revision_number,
        )

    async def save(self, revision: ChapterRevision) -> ChapterRevision:
        self._items[revision.id] = revision.model_copy(deep=True)
        return revision


class _HookRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, Hook] = {}

    async def get(self, hook_id: uuid.UUID) -> Hook | None:
        item = self._items.get(hook_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Hook]:
        return [item.model_copy(deep=True) for item in self._items.values() if item.project_id == project_id]

    async def save(self, hook: Hook) -> Hook:
        self._items[hook.id] = hook.model_copy(deep=True)
        return hook


class _ForeshadowRepo:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, Foreshadowing] = {}

    async def get(self, item_id: uuid.UUID) -> Foreshadowing | None:
        item = self._items.get(item_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Foreshadowing]:
        return [item.model_copy(deep=True) for item in self._items.values() if item.project_id == project_id]

    async def save(self, item: Foreshadowing) -> Foreshadowing:
        self._items[item.id] = item.model_copy(deep=True)
        return item
