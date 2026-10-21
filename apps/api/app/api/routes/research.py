from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status

from app.api.deps import get_engine, get_optional_llm_provider
from app.api.schemas import ConfirmBody, CreationPitch, ProjectFinalizeCreation, ResearchSessionOut, ResearchSourceCreate, ResearchSourceUpload, ResearchStageUpdate
from app.core.config import Settings, get_settings
from app.services.book_snapshot import save_project_snapshot
from app.services.work_tags import validate_work_tags
from novel_engine.domain.errors import InvalidStateError
from novel_engine.creative.contract import compile_creative_contract
from novel_engine.services.engine import NovelEngine
from novel_engine.models.entities import Character, ChapterPlan, MasterPlot, PlotBeat, ScenePlan, StoryArc, StoryBible, WorldBible, WorldRule
from novel_engine.models.enums import CharacterRole, IntensityLevel, NarrativeTense, PointOfView, ProjectStatus
from novel_engine.providers.base import LLMProvider
from novel_engine.research.executor import DistillationExecutor

router = APIRouter(tags=["research"])

STAGE_DEFS = (
    ("ingest", "导入与切分", "识别文件、章节边界、标题和文本质量"),
    ("analyze", "单本拆解", "逐本提取人物、冲突、节拍、视角和叙事手法"),
    ("scan", "题材与市场扫描", "对比开篇、钩子、节奏、卖点和读者承诺"),
    ("synthesis", "多本归纳", "把具体文本提升为可迁移的创作规律"),
    ("profile", "生成创作 Profile", "形成结构、文案、节奏和表达控制项"),
)


def _new_session() -> dict:
    return {
        "session_id": str(uuid4()),
        "status": "idle",
        "progress": 0,
        "stages": [
            {
                "id": stage_id,
                "title": title,
                "detail": detail,
                "status": "pending",
                "output": "尚未开始",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            for stage_id, title, detail in STAGE_DEFS
        ],
        "sources": [],
        "artifacts": [],
        "active_task": None,
    }


def _session(project) -> dict:
    research = (project.extra_metadata or {}).get("research")
    if not isinstance(research, dict):
        return _new_session()
    base = _new_session()
    base.update(research)
    # Older projects stored research without a stable session id.  Keep the
    # session recoverable while ensuring new creative output can bind to one
    # immutable research run.
    if not base.get("session_id"):
        base["session_id"] = str(uuid4())
    return base


def _save(project, research: dict):
    return project.model_copy(update={"extra_metadata": {**(project.extra_metadata or {}), "research": research}})


def _progress(research: dict) -> int:
    stages = research.get("stages", [])
    if not stages:
        return 0
    return round(sum(item.get("status") == "done" for item in stages) / len(stages) * 100)


def _artifact(research: dict, artifact_id: str, title: str, content: object, artifact_type: str) -> None:
    item = {"id": artifact_id, "title": title, "type": artifact_type, "content": content}
    research["artifacts"] = [old for old in research.get("artifacts", []) if old.get("id") != artifact_id]
    research["artifacts"].append(item)


def _source_public(source: dict) -> dict:
    return {key: value for key, value in source.items() if not key.startswith("_")}


async def _mark_stage_failure(engine: NovelEngine, project, research: dict, current: dict, exc: Exception) -> None:
    """Persist a failed stage before letting the normal API error handler respond."""
    current["status"] = "error"
    current["output"] = f"失败：{exc}"
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    research["progress"] = _progress(research)
    research["status"] = "failed"
    research["active_task"] = {
        "stage": current.get("id"),
        "status": "error",
        "message": str(exc),
    }
    await engine.update_project(_save(project, research))


@router.get("/projects/{project_id}/research", response_model=ResearchSessionOut)
async def get_research(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    project = await engine.get_project(project_id)
    research = _session(project)
    if (project.extra_metadata or {}).get("research", {}).get("session_id") != research.get("session_id"):
        project = await engine.update_project(_save(project, research))
    return _session(project)


@router.post("/projects/{project_id}/research/sources", response_model=ResearchSessionOut, status_code=status.HTTP_201_CREATED)
async def add_research_source(
    project_id: UUID,
    body: ResearchSourceCreate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    project = await engine.get_project(project_id)
    research = _session(project)
    research["sources"].append({"id": str(uuid4()), **body.model_dump(), "status": "queued"})
    draft_project = _save(project, research).model_copy(update={
        "status": ProjectStatus.DRAFT,
        "extra_metadata": {
            **(project.extra_metadata or {}),
            "research": research,
            "creation_status": "draft",
        },
    })
    saved = await engine.update_project(draft_project)
    await save_project_snapshot(engine, saved.id)
    return _session(saved)


@router.post("/projects/{project_id}/research/upload", response_model=ResearchSessionOut, status_code=status.HTTP_201_CREATED)
async def upload_research_source(
    project_id: UUID,
    body: ResearchSourceUpload,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if Path(body.filename).suffix.lower() not in {".md", ".markdown", ".txt"}:
        from novel_engine.domain.errors import InvalidStateError
        raise InvalidStateError("目前只支持 Markdown 和 TXT 文件")
    if len(body.content.encode("utf-8")) > 8 * 1024 * 1024:
        from novel_engine.domain.errors import InvalidStateError
        raise InvalidStateError("单个参考作品不能超过 8MB")
    project = await engine.get_project(project_id)
    root = Path(settings.save_root) / "research_sources" / str(project_id)
    root.mkdir(parents=True, exist_ok=True)
    filename = Path(body.filename).name
    destination = root / f"{uuid4().hex[:8]}-{filename}"
    destination.write_text(body.content, encoding="utf-8")
    research = _session(project)
    research["sources"].append({
        "id": str(uuid4()),
        "title": body.title or Path(filename).stem,
        "source_type": destination.suffix.lstrip(".") or "text",
        "path": str(destination.resolve()),
        "chapter_count": 0,
        "word_count": 0,
        "selected_dimensions": ["plot", "characters", "style", "narrative", "dialogue", "pacing", "continuity"],
        "status": "queued",
    })
    saved = await engine.update_project(_save(project, research))
    await save_project_snapshot(engine, saved.id)
    return _session(saved)


@router.post("/projects/{project_id}/research/start", response_model=ResearchSessionOut)
async def start_research(
    project_id: UUID,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    project = await engine.get_project(project_id)
    research = _session(project)
    research["status"] = "running"
    for index, stage in enumerate(research["stages"]):
        if stage["status"] != "done":
            stage["status"] = "running" if index == 0 else "pending"
            stage["output"] = "等待分析器执行" if index else "已排队，等待分析器"
    research["progress"] = _progress(research)
    saved = await engine.update_project(_save(project, research))
    await save_project_snapshot(engine, saved.id)
    return _session(saved)


@router.post("/projects/{project_id}/research/stages/{stage_id}", response_model=ResearchSessionOut)
async def complete_research_stage(
    project_id: UUID,
    stage_id: str,
    body: ResearchStageUpdate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    provider: Annotated[LLMProvider | None, Depends(get_optional_llm_provider)],
) -> dict:
    project = await engine.get_project(project_id)
    research = _session(project)
    current = next((item for item in research["stages"] if item["id"] == stage_id), None)
    if current is None:
        from novel_engine.domain.errors import NotFoundError
        raise NotFoundError("research stage not found")
    if body.execute:
        executor = DistillationExecutor()
        if not research.get("sources"):
            from novel_engine.domain.errors import InvalidStateError
            raise InvalidStateError("请先登记至少一个参考作品")
        if stage_id == "ingest":
            loaded = await executor.ingest(research["sources"])
            research["sources"] = [_source_public(item) for item in loaded]
            _artifact(research, "ingest", "章节切分结果", research["sources"], "ingest")
            current["output"] = f"已读取 {len(loaded)} 部作品，完成章节切分"
        elif stage_id == "analyze":
            if provider is None:
                from novel_engine.domain.errors import InvalidStateError
                raise InvalidStateError("分析阶段需要先配置 LLM API Key")
            loaded = await executor.ingest(research["sources"])
            research["active_task"] = {
                "stage": "analyze",
                "status": "running",
                "message": "正在准备分层采样",
            }
            await engine.update_project(_save(project, research))

            async def on_analysis_progress(update: dict):
                research["active_task"] = {
                    "stage": "analyze",
                    "status": "running" if update.get("phase") != "completed" else "completed",
                    **update,
                }
                for source in research.get("sources", []):
                    if source.get("id") == update.get("source_id"):
                        source["status"] = "analyzing" if update.get("phase") != "completed" else "analyzed"
                        source["current_sampled_chapters"] = update.get("sampled_chapter_numbers", [])
                        source["current_sampled_titles"] = update.get("sampled_chapter_titles", [])
                # Persist the live progress without replacing the local
                # `research["stages"]` list. Replacing it here detached the
                # `current` stage object in the caller, leaving analyze stuck
                # at 17% even after the model returned successfully.
                await engine.update_project(_save(project, research))

            try:
                analyses = await executor.analyze(provider, loaded, on_progress=on_analysis_progress)
            except Exception as exc:
                await _mark_stage_failure(engine, project, research, current, exc)
                raise
            _artifact(research, "analyze", "单本拆解结果", analyses, "analysis")
            current["output"] = f"已完成 {len(analyses)} 部作品的多维拆解"
            research["sources"] = [{**item, "status": "analyzed"} for item in research["sources"]]
            research["active_task"] = {"stage": "analyze", "status": "completed", "message": current["output"]}
        elif stage_id == "scan":
            loaded = await executor.ingest(research["sources"])
            scan = {
                "source_count": len(loaded),
                "chapter_count": sum(item.get("chapter_count", 0) for item in loaded),
                "word_count": sum(item.get("word_count", 0) for item in loaded),
                "average_chapter_chars": round(sum(chapter["chars"] for item in loaded for chapter in item.get("chapters", [])) / max(1, sum(item.get("chapter_count", 0) for item in loaded))),
                "dimensions": ["opening", "hooks", "pacing", "reader_promise", "title_blurb"],
            }
            _artifact(research, "scan", "题材与市场扫描", scan, "scan")
            current["output"] = f"完成 {scan['source_count']} 部作品的市场指标扫描"
        elif stage_id == "synthesis":
            if provider is None:
                from novel_engine.domain.errors import InvalidStateError
                raise InvalidStateError("归纳阶段需要先配置 LLM API Key")
            analyses = next((item.get("content") for item in research.get("artifacts", []) if item.get("id") == "analyze"), None)
            if not analyses:
                from novel_engine.domain.errors import InvalidStateError
                raise InvalidStateError("请先完成单本拆解")
            try:
                synthesis = await executor.synthesize(provider, analyses)
            except Exception as exc:
                await _mark_stage_failure(engine, project, research, current, exc)
                raise
            _artifact(research, "synthesis", "跨作品归纳结果", synthesis, "synthesis")
            current["output"] = f"归纳出 {len(synthesis.get('shared_patterns', []))} 条共性规律"
        elif stage_id == "profile":
            if provider is None:
                from novel_engine.domain.errors import InvalidStateError
                raise InvalidStateError("Profile 阶段需要先配置 LLM API Key")
            synthesis = next((item.get("content") for item in research.get("artifacts", []) if item.get("id") == "synthesis"), None)
            if not synthesis:
                from novel_engine.domain.errors import InvalidStateError
                raise InvalidStateError("请先完成多本归纳")
            try:
                profile = await executor.profile(provider, synthesis)
            except Exception as exc:
                await _mark_stage_failure(engine, project, research, current, exc)
                raise
            _artifact(research, "profile", "原创创作 Profile", profile, "profile")
            current["output"] = "已生成可注入原创项目的创作 Profile"
        current["status"] = "done"
    else:
        current["status"] = body.status
        current["output"] = body.output or ("已完成" if body.status == "done" else "处理中")
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
    index = next(index for index, item in enumerate(research["stages"]) if item["id"] == stage_id)
    if body.status == "done" and index + 1 < len(research["stages"]):
        following = research["stages"][index + 1]
        if following["status"] == "pending":
            following["status"] = "running"
            following["output"] = "等待分析器执行"
    research["progress"] = _progress(research)
    research["status"] = "completed" if research["progress"] == 100 else "running"
    saved = await engine.update_project(_save(project, research))
    await save_project_snapshot(engine, saved.id)
    return _session(saved)


async def _apply_framework_proposal(
    project_id: UUID,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    *,
    commit: bool = True,
    write_story_bible: bool = True,
) -> dict:
    if not body.confirmed_by or not body.confirmed_by.strip():
        from novel_engine.domain.errors import ApprovalRequiredError
        raise ApprovalRequiredError("confirmed_by is required to apply the framework proposal")
    project = await engine.get_project(project_id)
    research = _session(project)
    # Approval must be idempotent: retries, double clicks, and multiple tabs
    # must not re-apply the same framework proposal.
    if research.get("framework_confirmed_by"):
        return research
    artifact = next((item for item in research.get("artifacts", []) if item.get("id") == "framework_proposal"), None)
    proposal = (artifact or {}).get("content", {}).get("proposal")
    if not proposal:
        from novel_engine.domain.errors import InvalidStateError
        raise InvalidStateError("请先生成小说框架提案")

    def enum_or(value: str, enum_type, default):
        try:
            return enum_type(value)
        except ValueError:
            return default

    if write_story_bible:
        await engine.story_bibles.upsert(StoryBible(
            project_id=project_id,
            premise=proposal["premise"],
            theme=proposal["theme"],
            tone=proposal["tone"],
            narrative_style=proposal["narrative_style"],
            pov=enum_or(proposal.get("pov", "third_limited"), PointOfView, PointOfView.THIRD_LIMITED),
            tense=enum_or(proposal.get("tense", "past"), NarrativeTense, NarrativeTense.PAST),
            romance_level=enum_or(proposal.get("romance_level", "high"), IntensityLevel, IntensityLevel.HIGH),
            violence_level=enum_or(proposal.get("violence_level", "medium"), IntensityLevel, IntensityLevel.MEDIUM),
            heat_level=enum_or(proposal.get("heat_level", "medium"), IntensityLevel, IntensityLevel.MEDIUM),
            target_word_count=80_000,
            chapter_word_count=2_500,
            tropes=proposal.get("tropes", []),
            logline=proposal["logline"],
            synopsis=proposal["synopsis"],
            extra_metadata={"research_session_id": research.get("session_id"), "research_source_ids": [str(item.get("id")) for item in research.get("sources", [])]},
        ), commit=commit)
    plot = MasterPlot(
        project_id=project_id,
        title=proposal["title"],
        structure=proposal["plot_structure"],
        summary=proposal["plot_summary"],
        beats=[PlotBeat(**beat) for beat in proposal.get("beats", [])],
        is_active=True,
    )
    existing = next((item for item in await engine.master_plots.list(project_id) if item.is_active), None)
    if existing:
        plot = await engine.master_plots.update(plot.model_copy(update={"id": existing.id}), commit=commit)
    else:
        plot = await engine.master_plots.create(plot, commit=commit)

    world_data = proposal.get("world")
    if world_data:
        current_world = await engine.world_bibles.get(project_id)
        world_id = current_world.id if current_world else WorldBible(
            project_id=project_id,
            name=world_data["name"],
            summary=world_data["summary"],
        ).id
        await engine.world_bibles.upsert(WorldBible(
            id=world_id,
            project_id=project_id,
            name=world_data["name"],
            summary=world_data["summary"],
            geography=world_data.get("geography"),
            factions=world_data.get("factions", []),
            rules=[WorldRule(world_bible_id=world_id, **rule) for rule in world_data.get("rules", [])],
        ), commit=commit)

    existing_characters = await engine.characters.list(project_id)
    existing_names = {item.name.casefold() for item in existing_characters}
    for item in proposal.get("characters", []):
        name = item.get("name", "").strip()
        if not name or name.casefold() in existing_names:
            continue
        try:
            role = CharacterRole(item.get("role", "supporting"))
        except ValueError:
            role = CharacterRole.SUPPORTING
        await engine.characters.create(Character(
            project_id=project_id,
            **{**item, "name": name, "role": role},
        ), commit=commit)

    existing_arcs = await engine.story_arcs.list(project_id)
    existing_sequences = {item.sequence for item in existing_arcs}
    for item in proposal.get("arcs", []):
        if item.get("sequence") in existing_sequences:
            continue
        await engine.story_arcs.create(StoryArc(
            project_id=project_id,
            master_plot_id=plot.id,
            arc_type="main",
            **item,
        ), commit=commit)

    # Turn the launch cards into editable draft plans. They are deliberately
    # conservative seed plans: no prose is generated and all remain pending
    # human review. Re-applying a framework is idempotent per chapter number.
    seeded_arcs = await engine.story_arcs.list(project_id)
    seeded_characters = await engine.characters.list(project_id)
    character_names = [item.name for item in seeded_characters[:4]] or ["Protagonist"]
    bible = await engine.story_bibles.get(project_id)
    seen_chapter_numbers: set[int] = set()
    opening_cards = sorted(
        proposal.get("opening_chapters", []),
        key=lambda item: int(item.get("chapter_number", 0) or 0),
    )
    for card in opening_cards:
        try:
            chapter_number = int(card.get("chapter_number", 0))
        except (TypeError, ValueError):
            continue
        if chapter_number < 1:
            continue
        # The chapter number is the canonical identity within a project.
        # Ignore duplicate cards returned by the model.
        if chapter_number in seen_chapter_numbers:
            continue
        seen_chapter_numbers.add(chapter_number)
        chapter_title = str(card.get("title") or f"Chapter {chapter_number}").strip()
        existing_chapter = await engine.uow.chapters.get_by_number(project_id, chapter_number)
        existing_plan = (
            await engine.uow.chapter_plans.latest_for_chapter(existing_chapter.id)
            if existing_chapter else None
        )
        if existing_plan is not None:
            continue
        purpose = str(card.get("purpose") or "Advance the central story promise.").strip()
        conflict = str(card.get("conflict") or "The protagonist faces immediate resistance.").strip()
        emotional_turn = str(card.get("emotional_turn") or "Resolve becomes uncertainty.").strip()
        reveal = str(card.get("reveal") or "A new fact changes the protagonist's next choice.").strip()
        hook = str(card.get("hook") or "A question remains unresolved.").strip()
        location = str(card.get("location") or "Primary story setting").strip()
        saved_plan = await engine.chapter_plans.create(ChapterPlan(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            pov=bible.pov.value if bible else "third_limited",
            location=location,
            characters=character_names,
            chapter_goal=purpose,
            conflict=conflict,
            emotional_arc=emotional_turn,
            new_information=reveal,
            reveal=reveal,
            foreshadowing=str(card.get("foreshadowing") or "Plant a detail that can gain meaning later.").strip(),
            setup=str(card.get("setup") or purpose).strip(),
            payoff=str(card.get("payoff") or "The immediate question changes shape.").strip(),
            cliffhanger=hook,
        ), commit=commit)
        scenes = card.get("scenes") or [{
            "location": location,
            "goal": purpose,
            "conflict": conflict,
            "turning_point": reveal,
            "dialogue_goal": "Expose pressure, desire, or resistance without explaining every feeling.",
            "emotion": emotional_turn,
            "information_revealed": reveal,
            "ending": hook,
        }]
        for scene_number, scene in enumerate(scenes[:4], start=1):
            await engine.scene_plans.create(ScenePlan(
                chapter_plan_id=saved_plan.id,
                scene_number=scene_number,
                location=str(scene.get("location") or location).strip(),
                characters=character_names[:2],
                goal=str(scene.get("goal") or purpose).strip(),
                conflict=str(scene.get("conflict") or conflict).strip(),
                turning_point=str(scene.get("turning_point") or reveal).strip(),
                dialogue_goal=str(scene.get("dialogue_goal") or "Advance pressure through subtext.").strip(),
                emotion=str(scene.get("emotion") or emotional_turn).strip(),
                information_revealed=str(scene.get("information_revealed") or reveal).strip(),
                ending=str(scene.get("ending") or hook).strip(),
            ), commit=commit)
        arc = next(
            (
                item for item in seeded_arcs
                if (item.start_chapter_number is None or item.start_chapter_number <= chapter_number)
                and (item.end_chapter_number is None or item.end_chapter_number >= chapter_number)
            ),
            None,
        )
        if arc:
            # Use the chapter resolved by ChapterPlanService. Looking it up
            # again by number can fail for legacy or partially migrated data.
            chapter = await engine.uow.chapters.get(saved_plan.chapter_id)
            if chapter is not None:
                await engine.chapters.update(chapter.model_copy(update={"story_arc_id": arc.id}), commit=commit)
    research["framework_confirmed_by"] = body.confirmed_by.strip()
    research["framework_confirmation_note"] = body.note
    for item in research.get("artifacts", []):
        if item.get("id") == "framework_proposal":
            content = dict(item.get("content") or {})
            content["status"] = "approved"
            item["content"] = content
    research["creative_profile"] = {
        "profile": next(
            (item.get("content") for item in research.get("artifacts", []) if item.get("id") == "profile"),
            {},
        ),
        "style_guide": proposal.get("style_guide", ""),
        "chapter_plan_rules": proposal.get("chapter_plan_rules", []),
        "rhythm_controls": proposal.get("rhythm_controls", []),
        "relationship_progression": proposal.get("relationship_progression", []),
        "reader_promise": proposal.get("reader_promise", ""),
        "originality_notes": proposal.get("originality_notes", []),
        "hard_constraints": proposal.get("chapter_plan_rules", []),
        "anti_ai_rules": proposal.get("originality_notes", []),
        "opening_chapters": proposal.get("opening_chapters", []),
    }
    project = project.model_copy(update={
        "extra_metadata": {
            **(project.extra_metadata or {}),
        "creative_profile": research["creative_profile"],
        "workflow_policy": "strict_hitl",
        }
    })
    saved = await engine.update_project(_save(project, research), commit=commit)
    if commit:
        await save_project_snapshot(engine, saved.id)
    return _session(saved)


@router.post("/projects/{project_id}/framework-proposal")
async def create_framework_proposal(
    project_id: UUID,
    body: CreationPitch,
    engine: Annotated[NovelEngine, Depends(get_engine)],
    provider: Annotated[LLMProvider | None, Depends(get_optional_llm_provider)],
) -> dict:
    """Create a reviewable framework proposal from the confirmed creation pitch."""
    project = await engine.get_project(project_id)
    if body.work_tags:
        try:
            validate_work_tags(body.work_tags, allow_empty=False)
        except ValueError as exc:
            raise InvalidStateError(str(exc)) from exc
    research = _session(project)
    stages = research.get("stages") or []
    if research.get("status") != "completed" or not stages or not all(item.get("status") == "done" for item in stages):
        raise InvalidStateError("请先完成全部参考研究阶段")
    if research.get("session_id") != body.research_binding.session_id:
        raise InvalidStateError("研究会话与当前项目不匹配")
    source_ids = {str(item.get("id")) for item in research.get("sources", [])}
    if not set(body.research_binding.source_ids).issubset(source_ids):
        raise InvalidStateError("创作提案使用了未登记的参考作品")
    profile = next((item.get("content") for item in research.get("artifacts", []) if item.get("id") == "profile"), None)
    if not profile:
        raise InvalidStateError("请先生成原创创作 Profile")
    if provider is None:
        raise InvalidStateError("生成小说框架前需要配置 LLM API Key")
    proposal = await DistillationExecutor().generate_framework_proposal(
        provider,
        profile,
        {
            "title": body.premise[:80] or project.title,
            "genre": project.genre,
            "target_platform": project.target_platform,
            "language": project.language,
            "creation_proposal": body.model_dump(mode="json"),
            "creative_contract": compile_creative_contract(
                genre=project.genre,
                audience="女频" if project.language == "zh-CN" else "",
                core_promise=body.logline or body.synopsis,
                premise=body.premise,
                theme=body.theme,
                work_tags=body.work_tags,
                language=project.language,
            ),
        },
    )
    artifact = {
        "id": "framework_proposal",
        "title": "待确认的小说框架提案",
        "type": "framework_proposal",
        "content": {
            "proposal": proposal,
            "creation_proposal": body.model_dump(mode="json"),
            "research_binding": body.research_binding.model_dump(mode="json"),
            "creative_contract": compile_creative_contract(
                genre=project.genre,
                audience="女频" if project.language == "zh-CN" else "",
                core_promise=body.logline or body.synopsis,
                premise=body.premise,
                theme=body.theme,
                work_tags=body.work_tags,
                language=project.language,
            ),
            "status": "pending_confirmation",
        },
    }
    research["artifacts"] = [item for item in research.get("artifacts", []) if item.get("id") != "framework_proposal"] + [artifact]
    research["creation_proposal"] = {
        **body.model_dump(mode="json"),
        "status": "confirmed",
    }
    saved = await engine.update_project(_save(project, research))
    await save_project_snapshot(engine, saved.id)
    return {"proposal": proposal, "research_binding": body.research_binding.model_dump(mode="json"), "status": "pending_confirmation"}


@router.post("/projects/{project_id}/finalize-creation")
async def finalize_creation(
    project_id: UUID,
    body: ProjectFinalizeCreation,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> object:
    """Atomically finalize a research-backed book draft.

    LLM work happens before this endpoint.  This endpoint only validates the
    approved research binding and persists the project package in one DB
    transaction, so a later write cannot leave a partially-created book.
    """
    from novel_engine.domain.errors import ApprovalRequiredError

    if not body.confirmed_by.strip():
        raise ApprovalRequiredError("confirmed_by is required")
    if body.research_binding != body.pitch.research_binding:
        raise InvalidStateError("书名简介与最终创建使用的研究绑定不一致")
    if body.pitch.work_tags:
        try:
            validate_work_tags(body.pitch.work_tags, allow_empty=False)
        except ValueError as exc:
            raise InvalidStateError(str(exc)) from exc
    if not body.framework_confirmed:
        raise InvalidStateError("请先确认小说框架提案")

    project = await engine.get_project(project_id)
    research = _session(project)
    stages = research.get("stages") or []
    if research.get("status") != "completed" or not stages or not all(item.get("status") == "done" for item in stages):
        raise InvalidStateError("请先完成全部参考研究阶段")
    if research.get("session_id") != body.research_binding.session_id:
        raise InvalidStateError("研究会话与当前项目不匹配")
    available_source_ids = {str(item.get("id")) for item in research.get("sources", [])}
    if not set(body.research_binding.source_ids).issubset(available_source_ids):
        raise InvalidStateError("最终创建使用了未登记的参考作品")
    profile = next(
        (item.get("content") for item in research.get("artifacts", []) if item.get("id") == body.research_binding.profile_artifact_id),
        None,
    )
    if not profile:
        raise InvalidStateError("请先生成原创创作 Profile")
    framework_artifact = next((item for item in research.get("artifacts", []) if item.get("id") == "framework_proposal"), None)
    framework_content = (framework_artifact or {}).get("content", {})
    if framework_content.get("status") != "pending_confirmation":
        raise InvalidStateError("小说框架提案不存在或已失效")
    if framework_content.get("research_binding") != body.research_binding.model_dump(mode="json"):
        raise InvalidStateError("小说框架提案与当前研究绑定不一致")
    stored_creation_proposal = dict(framework_content.get("creation_proposal") or {})
    submitted_creation_proposal = body.pitch.model_dump(mode="json")
    # Keep old drafts valid: work_tags was added after earlier framework
    # artifacts had already been persisted.
    if not stored_creation_proposal.get("work_tags") and not submitted_creation_proposal.get("work_tags"):
        stored_creation_proposal.pop("work_tags", None)
        submitted_creation_proposal.pop("work_tags", None)
    if stored_creation_proposal != submitted_creation_proposal:
        raise InvalidStateError("创作提案已修改，请重新生成小说框架")
    if framework_content.get("proposal") != body.framework_proposal:
        raise InvalidStateError("提交的小说框架不是当前提案版本")

    existing_titles = [item for item in await engine.list_projects() if item.id != project_id]
    if any(item.title.strip().casefold() == body.title.strip().casefold() for item in existing_titles):
        from novel_engine.domain.errors import DuplicateError
        raise DuplicateError(f"project title already exists: {body.title}")

    try:
        # The research proposal remains the sole source for the framework in
        # this phase.  The user-confirmed pitch owns Story Bible fields; it is
        # written once below instead of being written and then overwritten.
        await _apply_framework_proposal(
            project_id,
            ConfirmBody(confirmed_by=body.confirmed_by, note="Finalized during book creation"),
            engine,
            commit=False,
            write_story_bible=False,
        )
        project = await engine.get_project(project_id)
        active_plots = await engine.master_plots.list(project_id)
        active_plot = next((item for item in active_plots if item.is_active), None)
        if active_plot is not None and active_plot.title != body.title.strip():
            await engine.master_plots.update(
                active_plot.model_copy(update={"title": body.title.strip()}),
                commit=False,
            )
        binding_metadata = body.research_binding.model_dump(mode="json")
        creative_contract = compile_creative_contract(
            genre=body.genre,
            audience=body.target_reader,
            core_promise=body.pitch.logline or body.pitch.synopsis,
            premise=body.pitch.premise,
            theme=body.pitch.theme,
            work_tags=body.pitch.work_tags,
            language=body.language,
        )
        updated_project = await engine.update_project(
            project.model_copy(update={
                "title": body.title.strip(),
                "status": ProjectStatus.PLANNING,
                "genre": body.genre,
                "language": body.language,
                "target_platform": body.target_platform,
                "chapter_count_target": body.chapter_count_target,
                "extra_metadata": {
                    **(project.extra_metadata or {}),
                    "creation_status": "created",
                    "research_binding": binding_metadata,
                    "creative_contract": creative_contract,
                    "work_tags": body.pitch.work_tags,
                    "story_focus_required": True,
                    **({"story_focus": body.story_focus.model_dump()} if body.story_focus else {}),
                },
            }),
            commit=False,
        )
        await engine.story_bibles.upsert(StoryBible(
            project_id=project_id,
            premise=body.pitch.premise,
            theme=body.pitch.theme,
            tone=body.genre.replace("_", " "),
            narrative_style="close third serial",
            pov=PointOfView.THIRD_LIMITED,
            tense=NarrativeTense.PAST,
            romance_level=IntensityLevel.HIGH,
            violence_level=IntensityLevel.MEDIUM,
            heat_level=IntensityLevel.MEDIUM,
            target_word_count=80_000,
            chapter_word_count=2_500 if body.language == "zh-CN" else 1_800,
            tropes=[body.genre],
            logline=body.pitch.logline,
            synopsis=body.pitch.synopsis,
            extra_metadata={"research_binding": binding_metadata, "target_reader": body.target_reader, "reading_tags": body.pitch.reading_tags, "content_tags": body.pitch.content_tags, "protagonist_names": body.pitch.protagonist_names, "work_tags": body.pitch.work_tags},
        ), commit=False)
        await engine.uow.commit()
    except Exception:
        await engine.uow.rollback()
        raise

    await save_project_snapshot(engine, updated_project.id)
    return updated_project
