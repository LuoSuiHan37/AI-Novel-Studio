from __future__ import annotations

from novel_engine.models.entities import NovelProject
from novel_engine.domain.errors import DuplicateError
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project
from novel_engine.services.character import CharacterService
from novel_engine.services.chapter import ChapterService
from novel_engine.services.chapter_plan import ChapterPlanService
from novel_engine.services.foreshadowing import ForeshadowingService
from novel_engine.services.hook import HookService
from novel_engine.services.master_plot import MasterPlotService
from novel_engine.services.pipeline import PipelineService
from novel_engine.services.revision import RevisionService
from novel_engine.services.scene_plan import ScenePlanService
from novel_engine.services.story_arc import StoryArcService
from novel_engine.services.story_bible import StoryBibleService
from novel_engine.services.world_bible import WorldBibleService


class NovelEngine:
    """Composition root for domain services. No FastAPI, no LLM agents."""

    def __init__(self, uow: NovelUnitOfWork) -> None:
        self.uow = uow
        self.pipeline = PipelineService(uow)
        self.story_bibles = StoryBibleService(uow)
        self.world_bibles = WorldBibleService(uow)
        self.characters = CharacterService(uow)
        self.master_plots = MasterPlotService(uow)
        self.story_arcs = StoryArcService(uow)
        self.chapters = ChapterService(uow)
        self.chapter_plans = ChapterPlanService(uow)
        self.scene_plans = ScenePlanService(uow)
        self.revisions = RevisionService(uow)
        self.hooks = HookService(uow)
        self.foreshadowings = ForeshadowingService(uow)

    async def create_project(self, project: NovelProject) -> NovelProject:
        existing = await self.uow.projects.list()
        if any(item.title.strip().casefold() == project.title.strip().casefold() for item in existing):
            raise DuplicateError(f"project title already exists: {project.title}")
        saved = await self.uow.projects.add(project)
        await self.uow.commit()
        return saved

    async def list_projects(self) -> list[NovelProject]:
        return await self.uow.projects.list()

    async def get_project(self, project_id) -> NovelProject:
        return await require_project(self.uow, project_id)

    async def update_project(self, project: NovelProject, *, commit: bool = True) -> NovelProject:
        current = await require_project(self.uow, project.id)
        saved = await self.uow.projects.save(
            current.model_copy(
                update={
                    "title": project.title,
                    "genre": project.genre,
                    "tropes": project.tropes,
                    "target_platform": project.target_platform,
                    "platform_book_id": project.platform_book_id,
                    "platform_book_title": project.platform_book_title,
                    "auto_publish_enabled": project.auto_publish_enabled,
                    "completed": project.completed,
                    "language": project.language,
                    "chapter_count_target": project.chapter_count_target,
                    "status": project.status,
                    "current_stage": current.current_stage,
                    "extra_metadata": project.extra_metadata,
                }
            )
        )
        if commit:
            await self.uow.commit()
        return saved

    async def delete_project(self, project_id) -> None:
        await require_project(self.uow, project_id)
        await self.uow.projects.delete(project_id)
        await self.uow.commit()
