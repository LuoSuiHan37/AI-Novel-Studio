from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import Actor, confirmed_by, get_actor, get_engine, get_workflow
from app.api.schemas import ActorOut, ConfirmBody, ProjectCreate, ProjectTitleSuggest, ProjectUpdate
from app.services.book_snapshot import save_project_snapshot
from novel_engine.agents.contracts import IdeaInput
from novel_engine.creative.profile import compile_creative_profile
from novel_engine.domain.errors import InvalidStateError, NotFoundError
from novel_engine.models.entities import StoryBible
from novel_engine.models.enums import ProjectStatus
from novel_engine.services.engine import NovelEngine
from novel_engine.workflows.agent_workflow import AgentWorkflow
from novel_engine.models.entities import NovelProject

router = APIRouter(tags=["projects"])


def _normalize_target_platform(language: str | None, platform: str | None) -> str | None:
    """Keep the bundled Chinese rules from being bypassed by the English default."""
    if (language or "").lower() in {"zh", "zh-cn"} and (not platform or platform == "alphanovel"):
        return "fanqie"
    return platform


@router.post("/projects/title-suggestion")
async def suggest_project_title(
    body: ProjectTitleSuggest,
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    if body.research_project_id is None or body.research_binding is None:
        raise InvalidStateError("书名和简介生成必须绑定已完成的参考研究")
    research_project = await engine.get_project(body.research_project_id)
    research = (research_project.extra_metadata or {}).get("research") or {}
    stages = research.get("stages") or []
    profile = next(
        (item.get("content") for item in research.get("artifacts", []) if item.get("id") == body.research_binding.profile_artifact_id),
        None,
    )
    source_ids = {str(item.get("id")) for item in research.get("sources", [])}
    if research.get("session_id") != body.research_binding.session_id:
        raise InvalidStateError("研究会话与当前项目不匹配")
    if not body.research_binding.source_ids or not set(body.research_binding.source_ids).issubset(source_ids):
        raise InvalidStateError("书名和简介生成必须绑定已登记的参考作品")
    if research.get("status") != "completed" or not stages or not all(item.get("status") == "done" for item in stages):
        raise InvalidStateError("请先完成全部参考研究阶段")
    if not profile:
        raise InvalidStateError("请先生成原创创作 Profile")
    existing_titles = [item.title for item in await engine.list_projects()]
    avoid = ", ".join(existing_titles) if existing_titles else "none"
    result = await workflow.propose_idea(
        IdeaInput(
            tropes=body.tropes or [body.genre],
            genre=body.genre,
            platform=body.target_platform,
            language=body.language,
            brief=(
                f"Author's core idea: {body.brief.strip() or 'No fixed idea; invent a fresh premise for this genre.'}\n"
                f"Create a consistent reader-facing book package for genre '{body.genre}'. "
                f"Do not reuse any existing title: {avoid}. Return a fresh title and synopsis."
                + f"\nUse these distilled, abstract craft findings as constraints, without copying plot or wording: {profile}"
            ),
        )
    )
    title = result.output.working_title.strip()
    duplicate = any(item.casefold() == title.casefold() for item in existing_titles)
    return {
        "title": title,
        "available": not duplicate,
        "existing_titles": existing_titles,
        "premise": result.output.premise,
        "theme": result.output.theme or result.output.premise,
        "logline": result.output.logline,
        "synopsis": result.output.synopsis or result.output.premise,
        "reading_tags": result.output.reading_tags,
        "content_tags": result.output.content_tags,
        "protagonist_names": result.output.protagonist_names,
        "research_binding": body.research_binding.model_dump(mode="json"),
    }


@router.post("/projects/{project_id}/title-suggestion")
async def suggest_existing_project_title(
    project_id: UUID,
    workflow: Annotated[AgentWorkflow, Depends(get_workflow)],
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    """Suggest a new title from the current book package and written chapters."""
    project = await engine.get_project(project_id)
    story = await engine.story_bibles.get(project_id)
    if story is None:
        raise NotFoundError("story bible is required before redefining the title")
    chapters = await engine.chapters.list(project_id)
    chapter_context = "\n".join(
        f"第{chapter.chapter_number}章《{chapter.title}》：{chapter.content[:700]}"
        for chapter in chapters[-8:]
        if chapter.content.strip()
    )
    submission = (story.extra_metadata or {}).get("fanqie_submission", {})
    brief = (
        "为已经创建完成的小说重新命名，只返回一个新的中文书名。\n"
        "书名必须贴合现有作品，不得改变题材、主线、人物关系或读者承诺；"
        "不要复用当前书名，不要使用空泛的‘霸总/重生/系统’拼接，不要使用违规、低俗或夸张标题。\n\n"
        f"当前书名：{project.title}\n"
        f"题材：{project.genre}\n"
        f"主题：{story.theme}\n"
        f"前提：{story.premise}\n"
        f"一句话简介：{story.logline or ''}\n"
        f"番茄作品简介：{story.synopsis or ''}\n"
        f"阅读标签：{', '.join(submission.get('reading_tags', []))}\n"
        f"内容标签：{', '.join(submission.get('content_tags', []))}\n"
        f"主角：{', '.join(submission.get('protagonist_names', []))}\n"
        f"已写章节：\n{chapter_context or '暂无正文，请根据作品介绍命名。'}"
    )
    result = await workflow.propose_idea(
        IdeaInput(
            tropes=project.tropes or [project.genre],
            genre=project.genre,
            platform=project.target_platform or "fanqie",
            language=project.language,
            brief=brief,
        )
    )
    title = result.output.working_title.strip()
    available = not any(item.title.casefold() == title.casefold() for item in await engine.list_projects())
    return {"title": title, "available": available, "current_title": project.title}


@router.get("/me", response_model=ActorOut)
async def me(actor: Annotated[Actor, Depends(get_actor)]) -> ActorOut:
    return ActorOut(id=actor.id, is_authenticated=actor.is_authenticated)


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> NovelProject:
    project = await engine.create_project(
        NovelProject(
            title=body.title,
            status=ProjectStatus.DRAFT,
            genre=body.genre,
            tropes=body.tropes,
            target_platform=_normalize_target_platform(body.language, body.target_platform) or "alphanovel",
            language=body.language,
            chapter_count_target=body.chapter_count_target,
            extra_metadata={
                "novel_contract": {
                    "planned_chapter_count": body.chapter_count_target,
                    "status": "draft",
                }
            },
        )
    )
    if body.premise and body.theme:
        await engine.story_bibles.upsert(
            StoryBible(
                project_id=project.id,
                premise=body.premise,
                theme=body.theme,
                tone=body.tone or body.genre.replace("_", " "),
                narrative_style="close third serial",
                target_word_count=80_000,
                chapter_word_count=2_500,
                tropes=body.tropes,
                logline=body.logline,
                synopsis=body.synopsis,
            )
        )
    await save_project_snapshot(engine, project.id)
    return project


@router.get("/projects")
async def list_projects(engine: Annotated[NovelEngine, Depends(get_engine)]) -> list[NovelProject]:
    return await engine.list_projects()


@router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> NovelProject:
    return await engine.get_project(project_id)


@router.patch("/projects/{project_id}")
async def patch_project(
    project_id: UUID,
    body: ProjectUpdate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> NovelProject:
    current = await engine.get_project(project_id)
    updates = body.model_dump(exclude_unset=True)
    if "language" in updates or "target_platform" in updates:
        updates["target_platform"] = _normalize_target_platform(
            updates.get("language", current.language),
            updates.get("target_platform", current.target_platform),
        )
    creative_profile = updates.pop("creative_profile", None)
    if creative_profile is not None:
        updates["extra_metadata"] = {
            **(current.extra_metadata or {}),
            "creative_profile": _compile_creative_profile(creative_profile),
        }
    if body.chapter_count_target is not None:
        updates["extra_metadata"] = {
            **(updates.get("extra_metadata") or current.extra_metadata or {}),
            "novel_contract": {
                **((current.extra_metadata or {}).get("novel_contract") or {}),
                "planned_chapter_count": body.chapter_count_target,
                "status": "draft",
            },
        }
    project = await engine.update_project(current.model_copy(update=updates))
    if body.premise and body.theme:
        await engine.story_bibles.upsert(
            StoryBible(
                project_id=project.id,
                premise=body.premise,
                theme=body.theme,
                tone=body.tone or project.genre.replace("_", " "),
                narrative_style="close third serial",
                target_word_count=80_000,
                chapter_word_count=2_500,
                tropes=project.tropes,
                logline=body.logline,
                synopsis=body.synopsis,
            )
        )
    await save_project_snapshot(engine, project.id)
    return project


@router.post("/projects/{project_id}/pipeline/advance")
async def advance_pipeline(
    project_id: UUID,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    actor: Annotated[Actor, Depends(get_actor)],
) -> NovelProject:
    """Explicit human confirmation to leave the current pipeline stage."""
    return await engine.pipeline.advance(
        project_id,
        confirmed_by=confirmed_by(body.confirmed_by, actor),
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> Response:
    await engine.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
