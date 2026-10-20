from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_engine
from app.api.deps import Actor
from app.api.schemas import AutoNextChapterBody, PlatformBindingBody
from app.db.models.automation import AutomationDailyQuota, AutomationNotification, AutomationSchedule, AutomationTask, PublishTask
from app.db.models.chapter import Chapter
from app.db.models.project import NovelProject
from app.core.config import get_settings
from app.services.platform_publishers import BrowserPlatformPublisher, get_platform_publisher
from app.db.models.llm import LLMConfig
from app.llm.factory import create_provider, provider_config_from_settings
from app.adapters.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.db.session import get_session_factory
from novel_engine.workflows.agent_workflow import AgentWorkflow
from app.api.routes.chapters import auto_generate_next_chapter, queue_chapter_draft_upload
from novel_engine.services.engine import NovelEngine

router = APIRouter(tags=["automation"])
logger = logging.getLogger("ai-novel-studio.automation")
SHANGHAI = ZoneInfo("Asia/Shanghai")
DAILY_PUBLISH_LIMIT = 4
FIXED_AUTOMATION_INTERVAL_MINUTES = 20
_queued_recovery_lock = asyncio.Lock()
_automation_worker_tasks: set[asyncio.Task] = set()
_automation_worker_ids: set[UUID] = set()


async def _platform_latest_chapter_number(session: AsyncSession, project: NovelProject, platform: str) -> int:
    """Return the live platform cursor, falling back to durable local state."""
    publisher = get_platform_publisher(platform, get_settings())
    if isinstance(publisher, BrowserPlatformPublisher):
        latest = await publisher.get_latest_chapter_number()
        if latest is not None:
            return latest
    latest = await session.scalar(
        select(PublishTask.platform_chapter_number)
        .where(
            PublishTask.project_id == project.id,
            PublishTask.platform == platform,
            PublishTask.status == "published",
        )
        .order_by(PublishTask.platform_chapter_number.desc())
    )
    return int(latest or 0)


def _spawn_automation_worker(task_id: UUID, project_id: UUID, *, name: str) -> None:
    worker = asyncio.create_task(_run_queued_generation(task_id, project_id), name=name)
    _automation_worker_tasks.add(worker)
    _automation_worker_ids.add(task_id)

    def finish(done: asyncio.Task) -> None:
        _automation_worker_tasks.discard(done)
        _automation_worker_ids.discard(task_id)
        if not done.cancelled() and done.exception() is not None:
            logger.error("Automation worker crashed: %s", done.exception(), exc_info=done.exception())

    worker.add_done_callback(finish)


async def _set_task_progress(
    task: AutomationTask,
    session: AsyncSession,
    *,
    stage: str,
    message: str,
    status: str | None = None,
    finished: bool = False,
) -> None:
    now = datetime.now(timezone.utc)
    history = list(task.stage_history or [])
    history.append({"stage": stage, "message": message, "at": now.isoformat()})
    task.current_stage = stage
    task.progress_message = message
    task.stage_history = history[-50:]
    task.heartbeat_at = now
    if status:
        task.status = status
    if finished:
        task.finished_at = now
    await session.commit()


async def _set_publish_progress(
    row: PublishTask,
    session: AsyncSession,
    *,
    stage: str,
    message: str,
    status: str | None = None,
    finished: bool = False,
) -> None:
    now = datetime.now(timezone.utc)
    history = list(row.stage_history or [])
    history.append({"stage": stage, "message": message, "at": now.isoformat()})
    row.current_stage = stage
    row.progress_message = message
    row.stage_history = history[-50:]
    row.heartbeat_at = now
    if status:
        row.status = status
    if row.started_at is None:
        row.started_at = now
    if finished:
        row.finished_at = now
    await session.commit()


async def _daily_quota(session: AsyncSession, project_id: UUID, platform: str, *, lock: bool = False) -> AutomationDailyQuota:
    today = datetime.now(SHANGHAI).date()
    statement = select(AutomationDailyQuota).where(
        AutomationDailyQuota.project_id == project_id,
        AutomationDailyQuota.platform == platform,
        AutomationDailyQuota.quota_date == today,
    )
    if lock:
        statement = statement.with_for_update()
    row = await session.scalar(statement)
    if row is None:
        row = AutomationDailyQuota(
            project_id=project_id,
            platform=platform,
            quota_date=today,
            daily_limit=DAILY_PUBLISH_LIMIT,
            published_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.flush()
    return row


async def _published_count(session: AsyncSession, project_id: UUID, platform: str) -> int:
    return (await _daily_quota(session, project_id, platform)).published_count


async def _cancel_automatic_work(session: AsyncSession, project_id: UUID) -> None:
    """Stop every unfinished automatic generation/upload operation.

    Completed publications are immutable history. Unfinished rows are kept so
    the user can see what was stopped, but no worker may treat them as
    publishable after automation is disabled.
    """
    now = datetime.now(timezone.utc)
    tasks = (await session.scalars(select(AutomationTask).where(
        AutomationTask.project_id == project_id,
        AutomationTask.status.in_(["queued", "running"]),
    ))).all()
    for task in tasks:
        task.status = "cancelled"
        task.current_stage = "cancelled"
        task.progress_message = "自动连载已关闭，任务已取消"
        task.finished_at = now
        task.heartbeat_at = now
    publish_tasks = (await session.scalars(select(PublishTask).where(
        PublishTask.project_id == project_id,
        PublishTask.status.in_(["pending", "uploading", "draft_uploaded", "awaiting_confirmation", "confirmed"]),
    ))).all()
    for task in publish_tasks:
        task.status = "cancelled"
        task.current_stage = "cancelled"
        task.progress_message = "自动上传已关闭，任务已取消"
        task.error_message = "自动正式发布和定时连载均已关闭"
        task.finished_at = now
        task.heartbeat_at = now


def _failure_guidance(exc: Exception) -> tuple[str, str]:
    """Turn a technical failure into a concrete user-facing checklist."""
    raw = str(exc)[:1000]
    lowered = raw.lower()
    if "all connection attempts failed" in lowered or "connection refused" in lowered or "timeout" in lowered:
        return "请检查当前 AI 提供商的 Base URL、网络代理和防火墙；当前任务正在使用已保存的提供商配置。", raw
    if any(key in lowered for key in ("cdp", "browser", "登录", "验证码", "selector")):
        return "请检查作者中心登录状态、Chrome 调试端口和平台页面选择器，然后重新启动 API。", raw
    if any(key in lowered for key in ("book", "书籍", "绑定", "platform_book")):
        return "请检查目标平台、平台书籍 ID 和平台书名是否与当前小说一致。", raw
    if any(key in lowered for key in ("llm", "model", "api key", "生成", "审核")):
        return "请检查 AI 模型配置、API Key 和章节生成/审核配置。", raw
    if any(key in lowered for key in ("database", "postgres", "sqlalchemy", "asyncpg")):
        return "请检查 PostgreSQL 是否启动，并确认 API 只运行一个实例后重试。", raw
    return "请先查看本任务的当前节点和失败原因；确认平台绑定、登录状态和 AI 配置后，再点击重试或重新启动任务。", raw


async def auto_publish_task(project_id: UUID, task_id: UUID, session: AsyncSession) -> dict:
    """Publish a draft only when the project switch is enabled and quota remains."""
    from novel_engine.domain.errors import InvalidStateError, NotFoundError

    project = await session.get(NovelProject, project_id)
    row = await session.get(PublishTask, task_id)
    if project is None or row is None or row.project_id != project_id:
        raise NotFoundError("自动发布任务不存在")
    if not project.auto_publish_enabled:
        return {"status": "awaiting_confirmation", "reason": "auto_publish_disabled"}
    if row.platform != project.target_platform:
        raise InvalidStateError("平台任务与作品标记不一致")
    if row.status not in {"draft_uploaded", "awaiting_confirmation"}:
        return {"status": row.status, "reason": "not_publishable"}
    quota = await _daily_quota(session, project_id, row.platform, lock=True)
    if quota.published_count >= quota.daily_limit:
        row.status = "quota_reached"
        row.current_stage = "quota_reached"
        row.progress_message = "今日已达到 4 章正式发布上限，等待明天继续"
        row.error_message = f"北京时间今日已正式发布 {quota.daily_limit} 章"
        await session.commit()
        return {"status": row.status, "published_count": quota.published_count}
    chapter = await session.get(Chapter, row.chapter_id)
    publisher = get_platform_publisher(row.platform, get_settings())
    if chapter is None or publisher is None:
        row.status = "failed"
        row.error_message = "章节或平台发布适配器不可用"
        await session.commit()
        return {"status": row.status}
    await _set_publish_progress(row, session, stage="publishing", message=f"正在正式发布第 {chapter.chapter_number} 章", status="publishing")
    row.attempts += 1
    try:
        result = await publisher.publish(
            {
                "title": chapter.title,
                "chapter_number": chapter.chapter_number,
                "content": chapter.content,
                "platform_book_id": project.platform_book_id,
                "contains_ai": True,
                "use_ai": True,
            },
            row.external_chapter_id,
        )
        row.status = "published"
        row.current_stage = "published"
        row.progress_message = f"第 {chapter.chapter_number} 章已正式发布"
        row.external_chapter_id = result.external_id or row.external_chapter_id
        row.response = {**(row.response or {}), "publish": result.response, "ai_confirmed": True}
        row.published_at = datetime.now(timezone.utc)
        chapter.status = "published"
        quota.published_count += 1
        row.finished_at = datetime.now(timezone.utc)
        row.heartbeat_at = row.finished_at
        await session.commit()
        return {"status": row.status, "published_count": quota.published_count}
    except Exception as exc:
        row.status = "failed"
        row.current_stage = "publish_failed"
        row.progress_message = "正式发布失败，需要检查后重试"
        row.finished_at = datetime.now(timezone.utc)
        row.error_message = str(exc)[:1000]
        await session.commit()
        return {"status": row.status, "error": row.error_message}


@router.get("/projects/{project_id}/automation/platform-binding")
async def get_platform_binding(project_id: UUID, engine: Annotated[NovelEngine, Depends(get_engine)]):
    project = await engine.get_project(project_id)
    return {
        "platform": project.target_platform,
        "platform_book_id": project.platform_book_id,
        "platform_book_title": project.platform_book_title,
    }


@router.put("/projects/{project_id}/automation/platform-binding")
async def save_platform_binding(
    project_id: UUID,
    body: PlatformBindingBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    project = await engine.get_project(project_id)
    if project.target_platform not in {"fanqie", "qidian", "qimao"}:
        from novel_engine.domain.errors import InvalidStateError
        raise InvalidStateError("当前作品没有可发布的平台标记")
    saved = await engine.update_project(project.model_copy(update={
        "platform_book_id": body.platform_book_id.strip(),
        "platform_book_title": body.platform_book_title.strip() if body.platform_book_title else None,
    }))
    return {
        "platform": saved.target_platform,
        "platform_book_id": saved.platform_book_id,
        "platform_book_title": saved.platform_book_title,
    }


@router.get("/projects/{project_id}/automation/settings")
async def get_automation_settings(
    project_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    project = await engine.get_project(project_id)
    chapters = await engine.chapters.list(project_id)
    platform = project.target_platform or ""
    published_today = await _published_count(session, project_id, platform) if platform in {"fanqie", "qidian", "qimao"} else 0
    published_total = len((await session.scalars(select(PublishTask).where(
        PublishTask.project_id == project_id,
        PublishTask.platform == platform,
        PublishTask.status == "published",
    ))).all()) if platform else 0
    platform_count = published_total
    schedule = await session.scalar(select(AutomationSchedule).where(AutomationSchedule.project_id == project_id))
    automation_running = bool(project.auto_publish_enabled and schedule and schedule.enabled)
    if automation_running and platform in {"fanqie", "qidian", "qimao"}:
        try:
            platform_count = await _platform_latest_chapter_number(session, project, platform)
        except Exception:
            # The settings page remains usable when a browser session is
            # temporarily unavailable; the scheduler will report the actual
            # failure in its durable task history.
            platform_count = published_total
    return {
        "auto_publish_enabled": project.auto_publish_enabled,
        "completed": project.completed,
        "target_chapter_count": project.chapter_count_target,
        "local_chapter_count": len(chapters),
        "platform_chapter_count": platform_count,
        "daily_limit": DAILY_PUBLISH_LIMIT,
        "published_today": published_today,
        "platform": platform,
    }


@router.put("/projects/{project_id}/automation/settings")
async def save_automation_settings(
    project_id: UUID,
    body: dict,
    session: Annotated[AsyncSession, Depends(get_db)],
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    from novel_engine.domain.errors import InvalidStateError
    project = await engine.get_project(project_id)
    enabled = bool(body.get("auto_publish_enabled", False))
    if enabled:
        if project.target_platform not in {"fanqie", "qidian", "qimao"}:
            raise InvalidStateError("请先设置番茄、起点或七猫平台标记")
        if not project.platform_book_id:
            raise InvalidStateError("请先绑定目标平台的书籍 ID")
        if project.completed:
            raise InvalidStateError("作品已经完本，不能开启自动连载")
    saved = await engine.update_project(project.model_copy(update={"auto_publish_enabled": enabled}))
    if not enabled:
        # Turning off the user-facing switch must also stop the durable timer.
        # Otherwise a previously enabled schedule can continue creating draft
        # and publish attempts until its next tick.
        schedule = await session.scalar(select(AutomationSchedule).where(AutomationSchedule.project_id == project_id))
        if schedule is not None:
            schedule.enabled = False
            schedule.next_run_at = None
            schedule.updated_at = datetime.now(timezone.utc)
        await _cancel_automatic_work(session, project_id)
        await session.commit()
    return {"auto_publish_enabled": saved.auto_publish_enabled, "completed": saved.completed}


async def _run_queued_generation(task_id: UUID, project_id: UUID) -> None:
    settings = get_settings()
    factory = get_session_factory(settings)
    try:
        async with factory() as session:
            task = await session.get(AutomationTask, task_id)
            project = await session.get(NovelProject, project_id)
            if task is None or project is None:
                return
            if not project.auto_publish_enabled:
                task.status = "cancelled"
                task.current_stage = "cancelled"
                task.progress_message = "自动正式发布已关闭，任务已取消"
                task.finished_at = datetime.now(timezone.utc)
                task.heartbeat_at = task.finished_at
                await session.commit()
                return
            task.status = "running"
            task.started_at = datetime.now(timezone.utc)
            await _set_task_progress(task, session, stage="generating", message=f"正在生成第 {task.chapter_number or '下一'} 章", status="running")
        async with factory() as session:
            task = await session.get(AutomationTask, task_id)
            project = await session.get(NovelProject, project_id)
            if task is None or project is None or not project.auto_publish_enabled:
                if task is not None:
                    task.status = "cancelled"
                    task.current_stage = "cancelled"
                    task.progress_message = "自动正式发布已关闭，任务已取消"
                    task.finished_at = datetime.now(timezone.utc)
                    task.heartbeat_at = task.finished_at
                    await session.commit()
                return
            llm_row = await session.scalar(
                select(LLMConfig).where(LLMConfig.project_id == project_id).order_by(LLMConfig.is_default.desc())
            )
            if llm_row is None:
                llm_row = await session.scalar(
                    select(LLMConfig).where(LLMConfig.project_id.is_(None)).order_by(LLMConfig.is_default.desc())
                )
            workflow = AgentWorkflow(create_provider(provider_config_from_settings(settings, row=llm_row)))
            engine = NovelEngine(SqlAlchemyUnitOfWork(session))
            result = await auto_generate_next_chapter(
                project_id,
                AutoNextChapterBody(max_attempts=task.max_attempts if task else 2),
                engine,
                workflow,
                Actor(id="automation-worker", is_authenticated=False),
                None,
            )
            await _set_task_progress(task, session, stage="reviewing", message=f"第 {result.get('chapter_number') or task.chapter_number or '下一'} 章正在审核", status="running")
            if result.get("completed"):
                project = await session.get(NovelProject, project_id)
                if project is None or not project.auto_publish_enabled:
                    await _cancel_automatic_work(session, project_id)
                    return
                await _set_task_progress(task, session, stage="uploading_draft", message=f"第 {result['chapter_number']} 章审核通过，正在上传平台草稿", status="running")
                await queue_chapter_draft_upload(
                    project_id,
                    result["chapter_number"],
                    {},
                    engine,
                )
                publish_row = await session.scalar(
                    select(PublishTask).where(
                        PublishTask.project_id == project_id,
                        PublishTask.local_chapter_number == result["chapter_number"],
                    )
                )
                if publish_row is not None:
                    await auto_publish_task(project_id, publish_row.id, session)
            if task is not None:
                task.status = "completed" if result.get("completed") else "needs_human_review"
                task.current_stage = "completed" if result.get("completed") else "needs_human_review"
                task.progress_message = "章节已生成并完成发布流程" if result.get("completed") else "章节审核未通过，需要人工处理"
                task.attempt_count = len(result.get("attempts") or [])
                task.result = {"chapter_number": result.get("chapter_number"), "review_status": result.get("review_status")}
                task.completed_at = datetime.now(timezone.utc)
                task.finished_at = task.completed_at
                task.heartbeat_at = task.completed_at
                await session.commit()
    except Exception as exc:
        async with factory() as session:
            task = await session.get(AutomationTask, task_id)
            if task is not None:
                guidance, raw_error = _failure_guidance(exc)
                task.status = "failed"
                task.current_stage = "failed"
                task.progress_message = "任务执行失败，需要查看错误信息"
                task.error_message = str(exc)[:1000]
                task.completed_at = datetime.now(timezone.utc)
                task.finished_at = task.completed_at
                task.heartbeat_at = task.completed_at
                session.add(
                    AutomationNotification(
                        project_id=project_id,
                        task_id=task_id,
                        level="error",
                        code="queued_generation_failed",
                        message=f"自动生成失败。下一步：{guidance}",
                        details={"error": raw_error, "guidance": guidance, "stage": task.current_stage},
                    )
                )
                await session.commit()


async def _recover_queued_tasks(*, retry_provider_failures: bool = False) -> int:
    """Claim persisted queued tasks after an API restart and resume them.

    Queue state is stored in PostgreSQL, while the worker coroutine lives in
    the API process.  A restart therefore has to recreate the in-memory
    coroutine explicitly; otherwise the task remains queued forever.
    """
    async with _queued_recovery_lock:
        settings = get_settings()
        factory = get_session_factory(settings)
        now = datetime.now(timezone.utc)
        recovered: list[tuple[UUID, UUID]] = []
        async with factory() as session:
            candidate_tasks = (
                await session.scalars(
                    select(AutomationTask)
                    .where(AutomationTask.status.in_(["queued", "running", "failed"]))
                    .order_by(AutomationTask.created_at)
                )
            ).all()
            queued_tasks = []
            for task in candidate_tasks:
                if task.id in _automation_worker_ids:
                    continue
                error_text = (task.error_message or "").lower()
                stale_recovering = task.status == "running" and task.current_stage == "recovering"
                should_retry_missing_key = task.status == "failed" and "api key is missing" in error_text
                should_retry_known_transient = task.status == "failed" and "chapter not found" in error_text
                should_retry_provider_failure = retry_provider_failures and task.status == "failed" and (
                    "all connection attempts failed" in error_text or "http error" in error_text
                )
                if should_retry_missing_key:
                    llm_row = await session.scalar(
                        select(LLMConfig)
                        .where(LLMConfig.project_id == task.project_id)
                        .order_by(LLMConfig.is_default.desc())
                    )
                    if llm_row is None:
                        llm_row = await session.scalar(
                            select(LLMConfig)
                            .where(LLMConfig.project_id.is_(None))
                            .order_by(LLMConfig.is_default.desc())
                        )
                    try:
                        provider_config = provider_config_from_settings(settings, row=llm_row)
                        should_retry_missing_key = bool(
                            provider_config.api_key and provider_config.api_key.get_secret_value().strip()
                        )
                    except Exception:
                        should_retry_missing_key = False
                if task.status != "queued" and not stale_recovering and not should_retry_missing_key and not should_retry_known_transient and not should_retry_provider_failure:
                    continue
                queued_tasks.append(task)
                task.status = "running"
                task.current_stage = "recovering"
                task.progress_message = (
                    "检测到 API Key 已恢复，正在自动重试任务"
                    if should_retry_missing_key
                    else "已修复章节定位问题，正在自动重试任务"
                    if should_retry_known_transient
                    else "已更新 AI 提供商配置，正在自动重试任务"
                    if should_retry_provider_failure
                    else "服务已恢复，正在接管排队任务"
                )
                task.stage_history = [
                    *(task.stage_history or []),
                    {
                        "stage": "recovering",
                        "message": task.progress_message,
                        "at": now.isoformat(),
                    },
                ][-50:]
                task.started_at = task.started_at or now
                task.heartbeat_at = now
                recovered.append((task.id, task.project_id))
            if queued_tasks:
                await session.commit()

        for task_id, project_id in recovered:
            _spawn_automation_worker(task_id, project_id, name=f"recover-automation-task-{task_id}")
    if recovered:
        logger.info("Recovered %s persisted automation task(s)", len(recovered))
    return len(recovered)


@router.post("/projects/{project_id}/automation/enqueue-next", status_code=202)
async def enqueue_next_chapter(
    project_id: UUID,
    body: AutoNextChapterBody,
    session: Annotated[AsyncSession, Depends(get_db)],
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    project = await engine.get_project(project_id)
    chapters = await engine.chapters.list(project_id)
    next_number = max((item.chapter_number for item in chapters), default=0) + 1
    active = await session.scalar(
        select(AutomationTask).where(
            AutomationTask.project_id == project_id,
            AutomationTask.chapter_number == next_number,
            AutomationTask.status.in_(["queued", "running"]),
        )
    )
    if active is not None:
        return active
    task = AutomationTask(
        project_id=project_id,
        task_type="generate_next_chapter",
        status="queued",
        chapter_number=next_number,
        max_attempts=body.max_attempts,
        payload={"human_notes": body.human_notes or ""},
        current_stage="queued",
        progress_message="已排队，等待后台开始生成",
        stage_history=[{"stage": "queued", "message": "已排队，等待后台开始生成", "at": datetime.now(timezone.utc).isoformat()}],
        heartbeat_at=datetime.now(timezone.utc),
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    _spawn_automation_worker(task.id, project_id, name=f"automation-task-{task.id}")
    return task


@router.get("/projects/{project_id}/automation/tasks")
async def list_automation_tasks(project_id: UUID, session: Annotated[AsyncSession, Depends(get_db)]):
    rows = await session.scalars(
        select(AutomationTask).where(AutomationTask.project_id == project_id).order_by(AutomationTask.created_at.desc()).limit(100)
    )
    return list(rows.all())


@router.get("/projects/{project_id}/automation/publish-tasks")
async def list_publish_tasks(project_id: UUID, session: Annotated[AsyncSession, Depends(get_db)]):
    rows = await session.scalars(
        select(PublishTask).where(PublishTask.project_id == project_id).order_by(PublishTask.created_at.desc())
    )
    return list(rows.all())


@router.get("/projects/{project_id}/automation/notifications")
async def list_automation_notifications(project_id: UUID, session: Annotated[AsyncSession, Depends(get_db)]):
    rows = await session.scalars(
        select(AutomationNotification)
        .where(AutomationNotification.project_id == project_id)
        .order_by(AutomationNotification.created_at.desc())
        .limit(100)
    )
    return list(rows.all())


@router.post("/projects/{project_id}/automation/notifications/{notification_id}/read")
async def mark_automation_notification_read(
    project_id: UUID,
    notification_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    row = await session.scalar(
        select(AutomationNotification).where(
            AutomationNotification.id == notification_id,
            AutomationNotification.project_id == project_id,
        )
    )
    if row is None:
        from novel_engine.domain.errors import NotFoundError
        raise NotFoundError("automation notification not found")
    row.read_at = datetime.now(timezone.utc)
    await session.commit()
    return row


@router.post("/projects/{project_id}/automation/publish-tasks/{task_id}/confirm")
async def confirm_publish_task(
    project_id: UUID,
    task_id: UUID,
    body: dict,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    from novel_engine.domain.errors import InvalidStateError, NotFoundError
    row = await session.scalar(
        select(PublishTask).where(PublishTask.id == task_id, PublishTask.project_id == project_id)
    )
    if row is None:
        raise NotFoundError("publish task not found")
    project = await session.get(NovelProject, project_id)
    if project is None or project.target_platform != row.platform:
        raise InvalidStateError("平台任务与作品的平台标记不一致，已阻止发布")
    if project.platform_book_id and row.platform_book_id and project.platform_book_id != row.platform_book_id:
        raise InvalidStateError("平台书籍绑定已变化，已阻止发布")
    confirmed_by = str(body.get("confirmed_by") or "").strip()
    if not confirmed_by:
        raise InvalidStateError("confirmed_by is required")
    if row.status not in {"draft_uploaded", "awaiting_confirmation"}:
        raise InvalidStateError(f"平台任务当前状态为 {row.status}，不能确认发布")
    row.status = "confirmed"
    row.response = {**(row.response or {}), "confirmed_by": confirmed_by, "confirmation_note": body.get("note")}
    chapter = await session.get(Chapter, row.chapter_id)
    if chapter is None:
        raise NotFoundError("chapter not found")
    publisher = get_platform_publisher(row.platform, get_settings())
    if publisher is None:
        raise InvalidStateError("该平台尚未配置上传适配器或授权凭据")
    quota = await _daily_quota(session, project_id, row.platform, lock=True)
    if quota.published_count >= quota.daily_limit:
        row.status = "quota_reached"
        row.error_message = f"北京时间今日已正式发布 {quota.daily_limit} 章"
        await session.commit()
        return {"task": row, "next_action": "quota_reached"}
    row.status = "publishing"
    row.attempts += 1
    try:
        result = await publisher.publish(
            {
                "title": chapter.title,
                "chapter_number": chapter.chapter_number,
                "content": chapter.content,
                "platform_book_id": project.platform_book_id,
                "contains_ai": True,
                "use_ai": True,
            },
            row.external_chapter_id,
        )
        row.status = "published"
        row.external_chapter_id = result.external_id or row.external_chapter_id
        row.response = {**(row.response or {}), "publish": result.response}
        row.published_at = datetime.now(timezone.utc)
        chapter.status = "published"
        quota.published_count += 1
    except Exception as exc:
        row.status = "failed"
        row.error_message = str(exc)[:1000]
        session.add(
            AutomationNotification(
                project_id=project_id,
                level="error",
                code="platform_publish_failed",
                message=f"{row.platform} 正式发布失败，需要重试。",
                details={"publish_task_id": str(row.id), "error": str(exc)[:1000]},
            )
        )
    await session.commit()
    return {"task": row, "next_action": "done" if row.status == "published" else "retry"}


@router.get("/projects/{project_id}/automation/schedule")
async def get_schedule(project_id: UUID, session: Annotated[AsyncSession, Depends(get_db)]):
    return await session.scalar(select(AutomationSchedule).where(AutomationSchedule.project_id == project_id))


@router.put("/projects/{project_id}/automation/schedule")
async def save_schedule(
    project_id: UUID,
    body: dict,
    session: Annotated[AsyncSession, Depends(get_db)],
    engine: Annotated[NovelEngine, Depends(get_engine)],
):
    await engine.get_project(project_id)
    row = await session.scalar(select(AutomationSchedule).where(AutomationSchedule.project_id == project_id))
    if row is None:
        now = datetime.now(timezone.utc)
        row = AutomationSchedule(project_id=project_id, created_at=now, updated_at=now)
        session.add(row)
    else:
        row.updated_at = datetime.now(timezone.utc)
    # A schedule cannot run independently of the master automatic-publishing
    # switch. This prevents stale UI state or an old timer from reactivating
    # uploads after the user has cancelled automation.
    row.enabled = bool(body.get("enabled", False)) and bool(project.auto_publish_enabled)
    row.interval_minutes = FIXED_AUTOMATION_INTERVAL_MINUTES
    row.max_attempts = max(1, min(int(body.get("max_attempts", 2)), 4))
    target_platform = (await engine.get_project(project_id)).target_platform
    row.platforms = [target_platform] if target_platform in {"fanqie", "qidian", "qimao"} else []
    row.next_run_at = datetime.now(timezone.utc) if row.enabled else None
    row.last_error = None
    if not row.enabled:
        await _cancel_automatic_work(session, project_id)
    await session.commit()
    await session.refresh(row)
    return row


async def _process_scheduled_project(project_id: UUID, factory, settings) -> None:
    """Run one project's scheduled cycle; callers may run several projects concurrently."""
    try:
        async with factory() as session:
            llm_row = await session.scalar(
                select(LLMConfig).where(LLMConfig.project_id == project_id).order_by(LLMConfig.is_default.desc())
            )
            if llm_row is None:
                llm_row = await session.scalar(
                    select(LLMConfig).where(LLMConfig.project_id.is_(None)).order_by(LLMConfig.is_default.desc())
                )
            workflow = AgentWorkflow(create_provider(provider_config_from_settings(settings, row=llm_row)))
            engine = NovelEngine(SqlAlchemyUnitOfWork(session))
            schedule = await session.scalar(select(AutomationSchedule).where(AutomationSchedule.project_id == project_id))
            project = await engine.get_project(project_id)
            chapters = await engine.chapters.list(project_id)
            platform = project.target_platform
            if not project.auto_publish_enabled or schedule is None or not schedule.enabled:
                return
            if project.completed or platform not in {"fanqie", "qidian", "qimao"}:
                return
            active = await session.scalar(select(AutomationTask).where(
                AutomationTask.project_id == project_id,
                AutomationTask.status.in_(["queued", "running"]),
            ))
            if active is not None:
                return
            if await _published_count(session, project_id, platform) >= DAILY_PUBLISH_LIMIT:
                return
            # The platform is the cursor. Never choose the first local
            # chapter that happens not to have a publish row: that can replay
            # chapter 1 after a restart or after the platform is ahead.
            platform_latest = await _platform_latest_chapter_number(session, project, platform)
            chapter_number = platform_latest + 1
            local_chapter = next(
                (item for item in chapters
                 if item.chapter_number == chapter_number and item.content.strip()),
                None,
            )
            target = project.chapter_count_target
            if target and chapter_number > target:
                return
            task = AutomationTask(
                project_id=project_id,
                task_type="scheduled_serialization",
                status="queued",
                chapter_number=chapter_number,
                max_attempts=schedule.max_attempts if schedule else 2,
                current_stage="queued",
                progress_message=f"已排队，准备处理第 {chapter_number} 章",
                stage_history=[{"stage": "queued", "message": f"已排队，准备处理第 {chapter_number} 章", "at": datetime.now(timezone.utc).isoformat()}],
                heartbeat_at=datetime.now(timezone.utc),
            )
            session.add(task)
            await session.commit()
            await _set_task_progress(task, session, stage="uploading_draft" if local_chapter else "generating", message=f"正在处理第 {chapter_number} 章", status="running")
            if local_chapter is None:
                result = await auto_generate_next_chapter(
                    project_id,
                    AutoNextChapterBody(max_attempts=task.max_attempts, target_chapter_number=chapter_number),
                    engine,
                    workflow,
                    Actor(id="scheduler", is_authenticated=False),
                    None,
                )
                if not result.get("completed"):
                    await _set_task_progress(task, session, stage="needs_human_review", message="章节审核未通过，需要人工处理", status="needs_human_review", finished=True)
                    return
                chapter_number = result["chapter_number"]
                await _set_task_progress(task, session, stage="reviewing", message=f"第 {chapter_number} 章生成完成，审核通过", status="running")
            project = await engine.get_project(project_id)
            if not project.auto_publish_enabled:
                await _cancel_automatic_work(session, project_id)
                return
            await _set_task_progress(task, session, stage="uploading_draft", message=f"正在上传第 {chapter_number} 章平台草稿", status="running")
            await queue_chapter_draft_upload(project_id, chapter_number, {}, engine)
            publish_row = await session.scalar(select(PublishTask).where(
                PublishTask.project_id == project_id,
                PublishTask.local_chapter_number == chapter_number,
                PublishTask.platform == platform,
            ))
            if publish_row is not None:
                # A previous local record may say published even though the
                # platform cursor proves that chapter was never added. Allow
                # this exact next chapter to be retried after the live check.
                if publish_row.status == "published" and chapter_number > platform_latest:
                    publish_row.status = "pending"
                    publish_row.external_chapter_id = None
                    publish_row.error_message = "平台章节列表未发现该章节，按平台进度重新上传"
                    await session.commit()
                    await queue_chapter_draft_upload(project_id, chapter_number, {}, engine)
                    publish_row = await session.scalar(select(PublishTask).where(
                        PublishTask.project_id == project_id,
                        PublishTask.local_chapter_number == chapter_number,
                        PublishTask.platform == platform,
                    ))
                await auto_publish_task(project_id, publish_row.id, session)
            task.status = "completed" if publish_row is not None and publish_row.status == "published" else "needs_human_review"
            task.current_stage = "completed" if task.status == "completed" else "waiting_publish"
            task.progress_message = "本章已完成生成、上传和正式发布" if task.status == "completed" else "本章已上传，等待发布处理"
            task.finished_at = datetime.now(timezone.utc) if task.status == "completed" else None
            task.heartbeat_at = datetime.now(timezone.utc)
            await session.commit()
    except Exception as exc:
        async with factory() as session:
            guidance, raw_error = _failure_guidance(exc)
            session.add(AutomationNotification(
                project_id=project_id,
                level="error",
                code="scheduled_generation_failed",
                message=f"定时连载执行失败。下一步：{guidance}",
                details={"error": raw_error, "guidance": guidance, "stage": "scheduled_serialization"},
            ))
            await session.commit()


async def _automation_scheduler_loop() -> None:
    """Small built-in scheduler for local deployments.

    It deliberately runs at a coarse one-minute cadence and claims a schedule
    before doing LLM work, so a restart can safely pick it up again.
    """
    while True:
        try:
            settings = get_settings()
            factory = get_session_factory(settings)
            now = datetime.now(timezone.utc)
            await _recover_queued_tasks()
            async with factory() as session:
                schedules = (
                    await session.scalars(
                        select(AutomationSchedule).where(
                            AutomationSchedule.enabled.is_(True),
                            (AutomationSchedule.next_run_at.is_(None) | (AutomationSchedule.next_run_at <= now)),
                        )
                    )
                ).all()
                claimed = []
                for row in schedules:
                    row.next_run_at = now + timedelta(minutes=FIXED_AUTOMATION_INTERVAL_MINUTES)
                    claimed.append(row.project_id)
                if claimed:
                    await session.commit()
            for project_id in claimed:
                await asyncio.gather(
                    *(_process_scheduled_project(item, factory, settings) for item in claimed),
                    return_exceptions=True,
                )
                break
                try:
                    async with factory() as session:
                        llm_row = await session.scalar(
                            select(LLMConfig).where(LLMConfig.project_id == project_id).order_by(LLMConfig.is_default.desc())
                        )
                        config = provider_config_from_settings(settings, row=llm_row)
                        workflow = AgentWorkflow(create_provider(config))
                        engine = NovelEngine(SqlAlchemyUnitOfWork(session))
                        schedule = await session.scalar(
                            select(AutomationSchedule).where(AutomationSchedule.project_id == project_id)
                        )
                        project = await engine.get_project(project_id)
                        chapters = await engine.chapters.list(project_id)
                        target = project.chapter_count_target
                        platform = project.target_platform
                        if project.completed:
                            continue
                        if platform not in {"fanqie", "qidian", "qimao"}:
                            continue
                        published_count = len((await session.scalars(select(PublishTask.id).where(
                            PublishTask.project_id == project_id,
                            PublishTask.platform == platform,
                            PublishTask.status == "published",
                        ))).all())
                        if target and len(chapters) >= target and published_count >= target:
                            await engine.update_project(project.model_copy(update={"completed": True}))
                            continue
                        if await _published_count(session, project_id, platform) >= DAILY_PUBLISH_LIMIT:
                            continue

                        published_chapter_ids = set((await session.scalars(select(PublishTask.chapter_id).where(
                            PublishTask.project_id == project_id,
                            PublishTask.platform == platform,
                            PublishTask.status == "published",
                        ))).all())
                        local_chapter = next(
                            (item for item in sorted(chapters, key=lambda value: value.chapter_number)
                             if item.content.strip() and item.id not in published_chapter_ids),
                            None,
                        )
                        if local_chapter is None:
                            if target and len(chapters) >= target:
                                continue
                            result = await auto_generate_next_chapter(
                                project_id,
                                AutoNextChapterBody(max_attempts=schedule.max_attempts if schedule else 2),
                                engine,
                                workflow,
                                Actor(id="scheduler", is_authenticated=False),
                                None,
                            )
                            if not result.get("completed"):
                                continue
                            chapter_number = result["chapter_number"]
                        else:
                            chapter_number = local_chapter.chapter_number
                        await queue_chapter_draft_upload(project_id, chapter_number, {}, engine)
                        publish_row = await session.scalar(
                            select(PublishTask).where(
                                PublishTask.project_id == project_id,
                                PublishTask.local_chapter_number == chapter_number,
                                PublishTask.platform == platform,
                            )
                        )
                        if publish_row is not None:
                            await auto_publish_task(project_id, publish_row.id, session)
                except Exception as exc:
                    async with factory() as notify_session:
                        guidance, raw_error = _failure_guidance(exc)
                        notify_session.add(
                            AutomationNotification(
                                project_id=project_id,
                                level="error",
                                code="scheduled_generation_failed",
                                message=f"定时连载执行失败。下一步：{guidance}",
                                details={"error": raw_error, "guidance": guidance, "stage": "scheduled_serialization"},
                            )
                        )
                        await notify_session.commit()
                    continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automation scheduler iteration failed")
        await asyncio.sleep(60)


def start_automation_scheduler() -> asyncio.Task:
    # Run recovery immediately at startup; do not wait for the first 60-second
    # scheduler tick.  The scheduler repeats recovery as a safety net.
    recovery = asyncio.create_task(_recover_queued_tasks(), name="recover-queued-automation-tasks")
    def report_recovery(task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.error("Initial automation recovery failed: %s", task.exception(), exc_info=task.exception())

    recovery.add_done_callback(report_recovery)
    return asyncio.create_task(_automation_scheduler_loop(), name="novel-automation-scheduler")
