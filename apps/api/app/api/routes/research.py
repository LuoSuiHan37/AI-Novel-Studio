from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status

from app.api.deps import get_engine, get_optional_llm_provider
from app.api.schemas import ConfirmBody, ResearchSessionOut, ResearchSourceCreate, ResearchSourceUpload, ResearchStageUpdate
from app.core.config import Settings, get_settings
from app.services.book_snapshot import save_project_snapshot
from novel_engine.services.engine import NovelEngine
from novel_engine.models.entities import Character, ChapterPlan, MasterPlot, PlotBeat, ScenePlan, StoryArc, StoryBible, WorldBible, WorldRule
from novel_engine.models.enums import CharacterRole, IntensityLevel, NarrativeTense, PointOfView
from novel_engine.providers.base import LLMProvider
from novel_engine.research.executor import DistillationExecutor

router = APIRouter(tags=["research"])

STAGE_DEFS = (
    ("ingest", "导入与切分", "识别文件、章节边界、标题和文本质量"),
    ("analyze", "单本拆解", "逐本提取人物、冲突、节拍、视角和叙事手法"),
    ("scan", "题材与市场扫描", "对比开篇、钩子、节奏、卖点和读者承诺"),
    ("synthesis", "多本归纳", "把具体文本提升为可迁移的创作规律"),
    ("profile", "生成创作 Profile", "形成结构、文案、节奏和表达控制项"),
    ("inject", "注入原创项目", "写入 Story Bible、主线和章节规划建议"),
)


def _new_session() -> dict:
    return {
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
        "injection_approved_by": None,
        "active_task": None,
    }


def _session(project) -> dict:
    research = (project.extra_metadata or {}).get("research")
    if not isinstance(research, dict):
        return _new_session()
    base = _new_session()
    base.update(research)
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
    return _session(await engine.get_project(project_id))


@router.post("/projects/{project_id}/research/sources", response_model=ResearchSessionOut, status_code=status.HTTP_201_CREATED)
async def add_research_source(
    project_id: UUID,
    body: ResearchSourceCreate,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    project = await engine.get_project(project_id)
    research = _session(project)
    research["sources"].append({"id": str(uuid4()), **body.model_dump(), "status": "queued"})
    saved = await engine.update_project(_save(project, research))
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
        elif stage_id == "inject":
            if provider is None:
                from novel_engine.domain.errors import InvalidStateError
                raise InvalidStateError("注入提案阶段需要先配置 LLM API Key")
            profile = next((item.get("content") for item in research.get("artifacts", []) if item.get("id") == "profile"), None)
            if not profile:
                from novel_engine.domain.errors import InvalidStateError
                raise InvalidStateError("请先生成创作 Profile")
            try:
                proposal = await executor.inject(provider, profile, {"title": project.title, "genre": project.genre, "target_platform": project.target_platform, "language": project.language})
            except Exception as exc:
                await _mark_stage_failure(engine, project, research, current, exc)
                raise
            _artifact(research, "inject", "待确认的项目注入包", {"proposal": proposal, "requires_human_approval": True}, "proposal")
            current["output"] = "已生成注入提案，等待人工确认"
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


@router.post("/projects/{project_id}/research/inject/approve", response_model=ResearchSessionOut)
async def approve_research_injection(
    project_id: UUID,
    body: ConfirmBody,
    engine: Annotated[NovelEngine, Depends(get_engine)],
) -> dict:
    if not body.confirmed_by or not body.confirmed_by.strip():
        from novel_engine.domain.errors import ApprovalRequiredError
        raise ApprovalRequiredError("confirmed_by is required to inject the research proposal")
    project = await engine.get_project(project_id)
    research = _session(project)
    # Approval must be idempotent: retries, double clicks, and multiple tabs
    # must not re-apply the same proposal.
    if research.get("injection_approved_by"):
        return research
    artifact = next((item for item in research.get("artifacts", []) if item.get("id") == "inject"), None)
    proposal = (artifact or {}).get("content", {}).get("proposal")
    if not proposal:
        from novel_engine.domain.errors import InvalidStateError
        raise InvalidStateError("请先完成原创创作 Profile 和注入提案")

    def enum_or(value: str, enum_type, default):
        try:
            return enum_type(value)
        except ValueError:
            return default

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
    ))
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
        plot = await engine.master_plots.update(plot.model_copy(update={"id": existing.id}))
    else:
        plot = await engine.master_plots.create(plot)

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
        ))

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
        ))

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
        ))

    # Turn the launch cards into editable draft plans. They are deliberately
    # conservative seed plans: no prose is generated and all remain pending
    # human review. Re-approving an injection is idempotent per chapter number.
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
        ))
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
            ))
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
                await engine.chapters.update(chapter.model_copy(update={"story_arc_id": arc.id}))
    research["injection_approved_by"] = body.confirmed_by.strip()
    research["injection_note"] = body.note
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
    saved = await engine.update_project(_save(project, research))
    await save_project_snapshot(engine, saved.id)
    return _session(saved)
