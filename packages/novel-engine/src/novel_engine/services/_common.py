from __future__ import annotations

import uuid

from novel_engine.domain.errors import NotFoundError
from novel_engine.models.entities import NovelProject
from novel_engine.ports.repositories import NovelUnitOfWork


async def require_project(uow: NovelUnitOfWork, project_id: uuid.UUID) -> NovelProject:
    project = await uow.projects.get(project_id)
    if project is None:
        raise NotFoundError("project not found")
    return project
