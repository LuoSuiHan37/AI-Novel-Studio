from __future__ import annotations

import uuid

from novel_engine.domain import approval
from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import MasterPlot
from novel_engine.models.enums import ApprovalStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.services._common import require_project


class MasterPlotService:
    def __init__(self, uow: NovelUnitOfWork) -> None:
        self._uow = uow

    async def get(self, plot_id: uuid.UUID) -> MasterPlot:
        plot = await self._uow.master_plots.get(plot_id)
        if plot is None:
            raise NotFoundError("master plot not found")
        return plot

    async def list(self, project_id: uuid.UUID) -> list[MasterPlot]:
        await require_project(self._uow, project_id)
        return await self._uow.master_plots.list_by_project(project_id)

    async def create(self, plot: MasterPlot) -> MasterPlot:
        await require_project(self._uow, plot.project_id)
        _validate_plot(plot)
        plot.status = ApprovalStatus.APPROVED
        if plot.is_active:
            await self._deactivate_others(plot.project_id, except_id=None)
        saved = await self._uow.master_plots.save(plot)
        await self._uow.commit()
        return saved

    async def update(self, plot: MasterPlot) -> MasterPlot:
        current = await self.get(plot.id)
        _validate_plot(plot)
        plot.status = ApprovalStatus.APPROVED
        saved = await self._uow.master_plots.save(plot)
        await self._uow.commit()
        return saved

    async def activate(self, plot_id: uuid.UUID) -> MasterPlot:
        plot = await self.get(plot_id)
        await self._deactivate_others(plot.project_id, except_id=plot.id)
        plot = plot.model_copy(update={"is_active": True})
        saved = await self._uow.master_plots.save(plot)
        await self._uow.commit()
        return saved

    async def submit_for_review(self, plot_id: uuid.UUID) -> MasterPlot:
        plot = await self.get(plot_id)
        if plot.status is ApprovalStatus.APPROVED:
            return plot
        approval.submit_for_review(plot)
        saved = await self._uow.master_plots.save(plot)
        await self._uow.commit()
        return saved

    async def approve(self, plot_id: uuid.UUID, *, confirmed_by: str) -> MasterPlot:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        plot = await self.get(plot_id)
        if plot.status is ApprovalStatus.APPROVED:
            return plot
        approval.approve(plot)
        saved = await self._uow.master_plots.save(plot)
        await self._uow.commit()
        return saved

    async def _deactivate_others(self, project_id: uuid.UUID, except_id: uuid.UUID | None) -> None:
        for item in await self._uow.master_plots.list_by_project(project_id):
            if except_id is not None and item.id == except_id:
                continue
            if item.is_active:
                item = item.model_copy(update={"is_active": False})
                await self._uow.master_plots.save(item)


def _validate_plot(plot: MasterPlot) -> None:
    if not plot.title.strip() or not plot.summary.strip():
        raise InvalidStateError("master plot title and summary are required")
    if len(plot.beats) < 3:
        raise InvalidStateError("master plot needs at least three beats")
