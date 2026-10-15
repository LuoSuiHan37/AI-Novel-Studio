from __future__ import annotations

from difflib import SequenceMatcher
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from novel_engine.agents.contracts import (
    ChapterPlannerInput,
    ChapterSummaryInput,
    CommercialReviewInput,
    CommercialReviewOutput,
    ContinuityInput,
    ContinuityOutput,
    EditorInput,
    HookAgentInput,
    MemoryAgentInput,
    MemoryAgentOutput,
    ReviseInput,
    ReviseOutput,
    WriterInput,
)
from novel_engine.domain.errors import InvalidStateError
from novel_engine.memory.models import (
    ChapterMemory,
    CharacterMemory,
    ContextPackage,
    MemoryProposal,
    RetrievalRequest,
    TimelineMemory,
)
from novel_engine.memory.retrieval import RetrievalPipeline
from novel_engine.memory.service import MemoryService
from novel_engine.models.entities import Chapter, ChapterPlan, ChapterRevision, Foreshadowing, Hook, ScenePlan
from novel_engine.models.enums import (
    ChapterStatus,
    ApprovalStatus,
    ContinuityVerdict,
    EpistemicStatus,
    ForeshadowStatus,
    Importance,
    MemoryLayer,
    MemoryType,
)
from novel_engine.presets.loader import resolve_style_bundle
from novel_engine.presets.models import StyleBundle
from novel_engine.prompts.loader import agent_prompts_root
from novel_engine.services.engine import NovelEngine
from novel_engine.style.anti_repetition import (
    RepetitionWarning,
    StyleHistory,
    assess_repetition,
    record_chapter,
)
from novel_engine.style.word_count import count_text_units
from novel_engine.style.signals import scan_continuity_signals
from novel_engine.style.canon import scan_context_alignment
from novel_engine.style.commercial import scan_commercial_quality
from novel_engine.style.chapter_repetition import scan_chapter_repetition
from novel_engine.style.chapter_relevance import scan_chapter_relevance
from novel_engine.style.completeness import escalate_verdict, scan_prose_completeness
from novel_engine.style.memory_continuity import scan_scene_handoffs
from novel_engine.workflows.agent_workflow import AgentWorkflow, ChapterPassBundle
from novel_engine.workflows.context import (
    build_writer_context,
    character_to_agent,
    package_brief,
    plan_to_agent,
    plot_to_outline,
    snippets_from_package,
    story_bible_to_architect,
)


class LoadedChapterContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_id: UUID
    chapter_number: int
    bible: object
    world: object
    arc: object | None
    plot: object | None
    plan: ChapterPlan
    scenes: list[ScenePlan]
    characters: list
    chapter: Chapter
    style: StyleBundle
    package: ContextPackage
    writer_context: object


class DraftResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    chapter: Chapter
    plan: ChapterPlan
    scenes: list[ScenePlan]
    scene_plan_proposal: object | None = None
    bundle: ChapterPassBundle
    continuity: ContinuityOutput
    revision_suggestion: ReviseOutput | None = None
    anti_repetition: list[RepetitionWarning] = Field(default_factory=list)
    package: ContextPackage
    persisted_revision: ChapterRevision | None = None
    requires_human_approval: bool = True
    advances_next_chapter: bool = False
    silent_overwrite_blocked: bool = True
    secondary_continuity: ContinuityOutput | None = None
    secondary_commercial: CommercialReviewOutput | None = None
    versions: list["ChapterVersion"] = Field(default_factory=list)
    length_ok: bool = True
    length_warning: str | None = None
    repetition_check: dict = Field(default_factory=dict)
    relevance_check: dict = Field(default_factory=dict)


class ChapterVersion(BaseModel):
    version: int
    word_count: int
    score: float | None
    prose: str | None = None
    selected: bool = False
    accepted: bool = True
    rejection_reason: str | None = None


class CommitResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    chapter: Chapter
    summary: object
    memory: MemoryAgentOutput
    hooks: list[Hook]
    foreshadowings: list[Foreshadowing]
    timeline: TimelineMemory
    character_states: list[CharacterMemory]
    advances_next_chapter: bool = False
    memory_validation: dict = Field(default_factory=dict)


def _revise_instruction() -> str:
    path = agent_prompts_root() / "pipeline" / "continuity_revise_instruction.txt"
    return path.read_text(encoding="utf-8").strip()


def _review_requires_revision(editor, continuity: ContinuityOutput) -> bool:
    dimensions = (
        "pacing",
        "dialogue",
        "emotion",
        "character_voice",
        "show_dont_tell",
        "repetition",
        "grammar",
        "hook_strength",
        "romantic_tension",
        "plot_progress",
    )
    below_target = any(getattr(editor, name).score < 7 for name in dimensions)
    return bool(editor.needs_human_review or below_target or continuity.findings)


def _build_revision_instruction(editor, continuity: ContinuityOutput) -> str:
    feedback = [editor.overall_notes.strip()]
    for name in (
        "pacing",
        "dialogue",
        "emotion",
        "character_voice",
        "show_dont_tell",
        "repetition",
        "grammar",
        "hook_strength",
        "romantic_tension",
        "plot_progress",
    ):
        dimension = getattr(editor, name)
        if dimension.score < 7:
            feedback.append(f"{name} ({dimension.score}/10): {dimension.notes}")
    for finding in continuity.findings:
        feedback.append(
            f"{finding.severity.value} {finding.category}: {finding.problem} "
            f"Evidence: {finding.evidence} Recommendation: {finding.recommendation}"
        )
    return f"{_revise_instruction()}\n\nReview findings to address:\n- " + "\n- ".join(
        item for item in feedback if item
    )


def _length_revision_instruction(*, count: int, minimum: int, maximum: int, target: int) -> str:
    if count > maximum:
        return (
            f"长度控制修订：当前正文计数为 {count}，必须压缩到 {minimum}-{maximum} 字，"
            f"目标约 {target} 字。删除重复环境描写、重复心理、解释性复述和不改变因果的闲聊；"
            "保留所有计划场景、主冲突、主角选择、选择代价、关键信息和动作型结尾。"
            "禁止新增事件，禁止改变人物关系和章末钩子。输出完整正文，不要说明过程。"
        )
    return (
        f"长度控制修订：当前正文计数为 {count}，必须补足到 {minimum}-{maximum} 字，"
        f"目标约 {target} 字。只补充计划内的动作、阻力、对话潜台词、环境压力和因果反应；"
        "禁止新增场景、支线人物或改变结局，不要用重复总结凑字数。输出完整正文，不要说明过程。"
    )


def _is_chinese_prose(prose: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in prose)


def is_local_revision(source: str, candidate: str, similarity: float) -> bool:
    source_words = count_text_units(source)
    candidate_words = count_text_units(candidate)
    if candidate_words < max(120, int(source_words * 0.5)):
        return False
    return similarity >= 0.60


def _version_score(editor, continuity: ContinuityOutput) -> float:
    errors = sum(item.severity is ContinuityVerdict.ERROR for item in continuity.findings)
    warnings = sum(item.severity is ContinuityVerdict.WARNING for item in continuity.findings)
    dimensions = (
        "pacing", "dialogue", "emotion", "character_voice", "show_dont_tell",
        "repetition", "grammar", "hook_strength", "romantic_tension", "plot_progress",
    )
    quality = sum(getattr(editor, name).score for name in dimensions) / len(dimensions)
    return quality - errors * 100 - warnings * 10


def _human_revision(revision: ChapterRevision | None) -> bool:
    if revision is None:
        return False
    return (revision.change_summary or "").lower().startswith("human")


class ChapterGenerationPipeline:
    """Automated-audit chapter factory. Failed audits never approve a draft."""

    def __init__(
        self,
        engine: NovelEngine,
        workflow: AgentWorkflow,
        memory: MemoryService,
        style_history: StyleHistory | None = None,
        review_workflow: AgentWorkflow | None = None,
    ) -> None:
        self.engine = engine
        self.workflow = workflow
        self.memory = memory
        self.style_history = style_history or StyleHistory()
        self.review_workflow = review_workflow

    async def load(self, project_id: UUID, chapter_number: int) -> LoadedChapterContext:
        project = await self.engine.get_project(project_id)
        if project.chapter_count_target is not None and chapter_number > project.chapter_count_target:
            raise InvalidStateError(
                f"chapter {chapter_number} exceeds the book target of {project.chapter_count_target} chapters"
            )
        if chapter_number > 1:
            previous = await self.engine.chapters.get_by_number(project_id, chapter_number - 1)
            if previous is None:
                raise InvalidStateError(
                    f"chapter {chapter_number - 1} must exist before generating chapter {chapter_number}"
                )
            if previous.status not in {ChapterStatus.APPROVED, ChapterStatus.PUBLISHED} or not previous.content.strip():
                raise InvalidStateError(
                    f"chapter {chapter_number - 1} must have non-empty approved prose "
                    f"before chapter {chapter_number} can be generated"
                )
        bible = await self.engine.story_bibles.get(project_id)
        if bible is None:
            raise InvalidStateError("story bible is required before generating a chapter")
        world = await self.engine.world_bibles.get(project_id)
        characters = await self.engine.characters.list(project_id)
        if not characters:
            raise InvalidStateError(
                "请先在「角色」页创建至少一个角色（如 Aria / Kael），再生成章节正文"
            )
        plots = await self.engine.master_plots.list(project_id)
        plot = next((item for item in plots if item.is_active), plots[0] if plots else None)
        arcs = await self.engine.story_arcs.list(project_id)
        chapter = await self.engine.chapters.get_by_number(project_id, chapter_number)
        plan = await self.engine.uow.chapter_plans.latest_for_chapter(chapter.id)
        if plan is None:
            raise InvalidStateError("create a chapter plan before generating")
        scenes = await self.engine.scene_plans.list(plan.id)
        arc = _current_arc(arcs, chapter_number)
        _require_approved_canon(
            bible=bible,
            world=world,
            characters=characters,
            plot=plot,
            arc=arc,
            plan=plan,
        )
        known_character_names = {
            name.strip().casefold()
            for item in characters
            for name in [item.name, *item.aliases]
            if name.strip()
        }
        planned_character_names = {
            name.strip()
            for name in [*plan.characters, *(name for scene in scenes for name in scene.characters)]
            if name.strip()
        }
        missing_character_names = sorted(
            name for name in planned_character_names if name.casefold() not in known_character_names
        )
        if missing_character_names:
            raise InvalidStateError(
                "chapter plan references characters absent from context: "
                + ", ".join(missing_character_names)
            )
        creative_profile = (project.extra_metadata or {}).get("creative_profile", {})
        style = resolve_style_bundle(
            platform_id=project.target_platform,
            novel_id=project.genre,
            language=project.language,
        )
        profile_style = creative_profile.get("style_guide", "") if isinstance(creative_profile, dict) else ""
        if profile_style:
            style = style.model_copy(update={"style_guide": f"{style.style_guide}\n{profile_style}"})
        self._ensure_global(project_id, bible, world, characters, plot)
        hooks = await self.engine.hooks.list(project_id, open_only=True)
        retrieval = RetrievalPipeline(self.memory.store, self.memory.embedder)
        package = retrieval.retrieve(
            RetrievalRequest(
                project_id=project_id,
                chapter_number=chapter_number,
                chapter_title=plan.chapter_title,
                pov=plan.pov,
                location=plan.location,
                characters=list(plan.characters),
                locations=[plan.location, *[item.location for item in scenes]],
                current_arc=arc.summary if arc else None,
                chapter_goal=plan.chapter_goal,
                conflict=plan.conflict,
                active_hooks=[item.description for item in hooks],
            )
        )
        notes = tuple(
            f"{item.category}: {item.item} (x{item.frequency})"
            for item in assess_repetition(
                prose="",
                chapter_number=chapter_number,
                location=plan.location,
                conflict=plan.conflict,
                history=self.style_history,
                watchlist=style.platform.monitored_phrases,
            )
        )
        previous_chapter = await self.engine.chapters.get_by_number(project_id, chapter_number - 1) if chapter_number > 1 else None
        previous_memory = self.memory.store.chapter(project_id, chapter_number - 1) if chapter_number > 1 else None
        writer_context = build_writer_context(
            bible=bible,
            world=world,
            characters=characters,
            plan=plan,
            scenes=scenes,
            open_hooks=[item.description for item in hooks],
            current_arc=arc.summary if arc else "",
            style_guide=(
                f"{style.style_guide}\n"
                f"Writing contract: this chapter must contain {style.platform.chapter_word_min}-"
                f"{style.platform.chapter_word_max} counted units. "
                f"There are {max(1, len(scenes))} planned scenes; distribute the length across them "
                "so every scene has concrete action, conflict, dialogue or interaction, an emotional "
                "change, and new information. Do not pad with repeated descriptions or summaries."
            ),
            anti_repetition_notes=notes,
            memory_brief=package_brief(package),
            memories=snippets_from_package(package),
            forbidden_knowledge=package.forbidden_knowledge,
            previous_chapter_summary=_previous_chapter_context(
                previous_chapter=previous_chapter,
                previous_memory=previous_memory,
            ),
            language=project.language,
            creative_profile=creative_profile,
            chapter_word_min=style.platform.chapter_word_min,
            chapter_word_max=style.platform.chapter_word_max,
        )
        return LoadedChapterContext(
            project_id=project_id,
            chapter_number=chapter_number,
            bible=bible,
            world=world,
            arc=arc,
            plot=plot,
            plan=plan,
            scenes=scenes,
            characters=characters,
            chapter=chapter,
            style=style,
            package=package,
            writer_context=writer_context,
        )

    async def _normalize_length(self, prose: str, loaded: LoadedChapterContext) -> tuple[str, bool]:
        """Return a platform-compliant candidate, or the last candidate if repair failed."""
        if not _is_chinese_prose(prose):
            return prose, True

        minimum = loaded.writer_context.chapter_word_min
        maximum = loaded.writer_context.chapter_word_max
        target = loaded.writer_context.chapter_plan.target_word_count or round((minimum + maximum) / 2)
        for _ in range(3):
            count = count_text_units(prose)
            if minimum <= count <= maximum:
                return prose, True
            corrected = await self.workflow.revise.run(
                ReviseInput(
                    instruction=_length_revision_instruction(
                        count=count,
                        minimum=minimum,
                        maximum=maximum,
                        target=target,
                    ),
                    source_prose=prose,
                )
            )
            candidate = corrected.output.prose
            if not candidate.strip() or candidate == prose:
                break
            prose = candidate
        return prose, minimum <= count_text_units(prose) <= maximum

    async def draft(
        self,
        project_id: UUID,
        chapter_number: int,
        *,
        human_notes: str | None = None,
        generate_scenes: bool = False,
        persist: bool = False,
        overwrite_human: bool = False,
        created_by: str = "writer-agent",
    ) -> DraftResult:
        loaded = await self.load(project_id, chapter_number)
        scene_proposal = None
        scenes = loaded.scenes
        if generate_scenes:
            if loaded.plot is None:
                raise InvalidStateError("master plot is required to generate a scene plan")
            previous = self.memory.store.chapter(project_id, chapter_number - 1)
            scene_proposal = await self.workflow.propose_chapter_plan(
                ChapterPlannerInput(
                    story_bible=story_bible_to_architect(loaded.bible),
                    outline=plot_to_outline(loaded.plot, [loaded.arc] if loaded.arc else []),
                    characters=[character_to_agent(item) for item in loaded.characters],
                    chapter_number=chapter_number,
                    previous_chapter_summary=previous.summary if previous else None,
                    style_guide=loaded.style.style_guide,
                    current_arc=loaded.arc.summary if loaded.arc else "",
                    language=loaded.writer_context.language,
                )
            )
        if not scenes:
            raise InvalidStateError("add at least one scene plan before generating")

        writer_input = WriterInput(context=loaded.writer_context, human_notes=human_notes)
        if hasattr(self.workflow, "draft_chapter_by_scenes"):
            bundle = await self.workflow.draft_chapter_by_scenes(writer_input)
        else:
            bundle = await self.workflow.draft_chapter_pass(writer_input)
        prose, length_ok = await self._normalize_length(bundle.writer.output.prose, loaded)
        length_warning = None
        if not length_ok and _is_chinese_prose(prose):
            count = count_text_units(prose)
            minimum = loaded.writer_context.chapter_word_min
            maximum = loaded.writer_context.chapter_word_max
            length_warning = (
                f"正文当前为 {count} 字，目标范围为 {minimum}-{maximum} 字；"
                "已保留正文，可继续人工压缩或补写。"
            )
        signal_findings = scan_continuity_signals(
            prose=prose,
            world_rules=list(loaded.writer_context.world_rules),
            signals=loaded.style.signals(),
        )
        alignment_findings = scan_context_alignment(prose=prose, context=loaded.writer_context)
        completeness_findings = scan_prose_completeness(prose)
        continuity = ContinuityOutput(
            overall=escalate_verdict(bundle.continuity.output.overall, [
                *bundle.continuity.output.findings,
                *signal_findings,
                *alignment_findings,
                *completeness_findings,
                *scan_commercial_quality(prose=prose, context=loaded.writer_context),
            ]),
            findings=[
                *bundle.continuity.output.findings,
                *signal_findings,
                *alignment_findings,
                *completeness_findings,
                *scan_commercial_quality(prose=prose, context=loaded.writer_context),
            ],
        )
        secondary_continuity = None
        secondary_commercial = None
        initially_reviewed_prose = prose
        if self.review_workflow is not None:
            secondary_continuity = (
                await self.review_workflow.continuity.run(
                    ContinuityInput(context=loaded.writer_context, prose=prose)
                )
            ).output
            continuity = ContinuityOutput(
                overall=continuity.overall,
                findings=[*continuity.findings, *secondary_continuity.findings],
            )
            secondary_commercial = (
                await self.review_workflow.review_commercial(
                    CommercialReviewInput(context=loaded.writer_context, prose=prose)
                )
            ).output
        bundle = bundle.model_copy(
            update={"continuity": bundle.continuity.model_copy(update={"output": continuity})}
        )

        revision_suggestion = None
        versions = [
            ChapterVersion(
                version=1,
                prose=prose,
                word_count=count_text_units(prose),
                score=(
                    _version_score(bundle.editor.output, continuity)
                    if self.review_workflow is not None
                    else None
                ),
            )
        ]
        # V1 plus at most two targeted revisions. Every candidate is based on
        # the current version; no fresh chapter generation is performed here.
        for version_number in (2, 3):
            if self.review_workflow is None:
                # Never let the generation model revise its own draft. Without
                # an independent reviewer, V1 is the only valid candidate.
                break
            if not _review_requires_revision(bundle.editor.output, continuity):
                break
            instruction = _build_revision_instruction(bundle.editor.output, continuity)
            revised = await self.workflow.revise.run(
                ReviseInput(instruction=instruction, source_prose=prose)
            )
            revision_suggestion = revised.output
            candidate, length_ok = await self._normalize_length(revised.output.prose, loaded)
            similarity = SequenceMatcher(None, prose, candidate).ratio()
            if not length_ok:
                versions.append(
                    ChapterVersion(
                        version=version_number,
                        prose=candidate,
                        word_count=count_text_units(candidate),
                        score=-100000.0,
                        accepted=False,
                        rejection_reason=(
                            f"candidate is outside the platform range "
                            f"{loaded.writer_context.chapter_word_min}-"
                            f"{loaded.writer_context.chapter_word_max} words"
                        ),
                    )
                )
                break
            if not is_local_revision(prose, candidate, similarity):
                versions.append(
                    ChapterVersion(
                        version=version_number,
                        prose=candidate,
                        word_count=count_text_units(candidate),
                        score=-100000.0,
                        accepted=False,
                        rejection_reason="candidate is truncated or rewrites too much of the source",
                    )
                )
                break
            candidate_bundle, candidate_continuity, candidate_secondary = await self._review_candidate(
                loaded=loaded,
                bundle=bundle,
                prose=candidate,
            )
            candidate_score = _version_score(candidate_bundle.editor.output, candidate_continuity)
            current_score = _version_score(bundle.editor.output, continuity)
            versions.append(
                ChapterVersion(
                    version=version_number,
                    prose=candidate,
                    word_count=count_text_units(candidate),
                    score=candidate_score,
                    accepted=candidate_score >= current_score,
                    rejection_reason=None if candidate_score >= current_score else "not better than the previous version",
                )
            )
            if candidate_score < current_score:
                break
            prose = candidate
            bundle = candidate_bundle
            continuity = candidate_continuity
            secondary_continuity = candidate_secondary

        valid_versions = [
            item
            for item in versions
            if item.accepted
            and (
                not _is_chinese_prose(item.prose or "")
                or loaded.writer_context.chapter_word_min <= item.word_count <= loaded.writer_context.chapter_word_max
            )
        ]
        if not valid_versions:
            valid_versions = [item for item in versions if item.accepted]
        selected_version = max(valid_versions, key=lambda item: item.score)
        for item in versions:
            item.selected = item.version == selected_version.version

        # The pass bundle already contains memory/hook proposals for the
        # current prose. Re-run those agents only when a later revision
        # actually changed the prose; otherwise avoid duplicate LLM calls and
        # keep the provider contract deterministic.
        bundle_prose = bundle.writer.output.prose
        if prose == bundle_prose:
            final_memory = bundle.memory
            final_hooks = bundle.hooks
        else:
            final_memory = await self.workflow.memory.run(
                MemoryAgentInput(
                    chapter_number=chapter_number,
                    prose=prose,
                    chapter_plan=loaded.writer_context.chapter_plan,
                )
            )
            final_hooks = await self.workflow.hook.run(
                HookAgentInput(
                    chapter_number=chapter_number,
                    chapter_plan=loaded.writer_context.chapter_plan,
                    prose=prose,
                )
            )
        bundle = bundle.model_copy(update={"memory": final_memory, "hooks": final_hooks})
        bundle = bundle.model_copy(
            update={
                "writer": bundle.writer.model_copy(
                    update={
                        "output": bundle.writer.output.model_copy(
                            update={"prose": prose, "word_count": count_text_units(prose)}
                        )
                    }
                )
            }
        )
        # A revision can change the text after the first commercial audit.
        # Re-audit the selected final prose so approval never relies on a
        # review of an earlier version.
        if self.review_workflow is not None and prose != initially_reviewed_prose:
            secondary_commercial = (
                await self.review_workflow.review_commercial(
                    CommercialReviewInput(context=loaded.writer_context, prose=prose)
                )
            ).output

        final_count = count_text_units(prose)
        is_chinese_prose = any("\u3400" <= char <= "\u9fff" for char in prose)
        final_length_ok = not is_chinese_prose or (
            loaded.writer_context.chapter_word_min <= final_count <= loaded.writer_context.chapter_word_max
        )
        if is_chinese_prose and not final_length_ok:
            length_ok = False
            length_warning = (
                f"正文当前为 {final_count} 字，目标范围为 "
                f"{loaded.writer_context.chapter_word_min}-{loaded.writer_context.chapter_word_max} 字；"
                "已允许保存，请在编辑器中继续调整。"
            )

        anti = assess_repetition(
            prose=prose,
            chapter_number=chapter_number,
            location=loaded.plan.location,
            conflict=loaded.plan.conflict,
            history=self.style_history,
            watchlist=loaded.style.platform.monitored_phrases,
        )
        anti = [*anti, *_beat_warnings(loaded.plan, loaded.style), *_word_warnings(prose, loaded.style)]

        repetition_check = scan_chapter_repetition(
            chapter_number=chapter_number,
            content=prose,
            chapters=await self.engine.chapters.list(project_id),
        )
        relevance_check = scan_chapter_relevance(content=prose, plan=loaded.plan, scenes=loaded.scenes)

        persisted = None
        if persist:
            persisted = await self.persist_revision(
                project_id,
                chapter_number,
                prose,
                created_by=created_by,
                change_summary="writer-agent draft",
                overwrite_human=overwrite_human,
            )
        chapter = await self.engine.chapters.get_by_number(project_id, chapter_number)
        return DraftResult(
            chapter=chapter,
            plan=loaded.plan,
            scenes=scenes,
            scene_plan_proposal=scene_proposal.output if scene_proposal else None,
            bundle=bundle,
            continuity=continuity,
            revision_suggestion=revision_suggestion,
            anti_repetition=anti,
            package=loaded.package,
            persisted_revision=persisted,
            secondary_continuity=secondary_continuity,
            secondary_commercial=secondary_commercial,
            versions=versions,
            length_ok=final_length_ok,
            length_warning=length_warning,
            repetition_check=repetition_check.model_dump(),
            relevance_check=relevance_check.model_dump(),
        )

    async def _review_candidate(self, *, loaded, bundle, prose):
        editor_result = await self.workflow.editor.run(
            EditorInput(context=loaded.writer_context, prose=prose)
        )
        continuity_result = await self.workflow.continuity.run(
            ContinuityInput(context=loaded.writer_context, prose=prose)
        )
        findings = [
            *continuity_result.output.findings,
            *scan_continuity_signals(
                prose=prose,
                world_rules=list(loaded.writer_context.world_rules),
                signals=loaded.style.signals(),
            ),
            *scan_context_alignment(prose=prose, context=loaded.writer_context),
            *scan_prose_completeness(prose),
            *scan_commercial_quality(prose=prose, context=loaded.writer_context),
        ]
        continuity = ContinuityOutput(
            overall=escalate_verdict(continuity_result.output.overall, findings),
            findings=findings,
        )
        secondary = None
        if self.review_workflow is not None:
            secondary = (
                await self.review_workflow.continuity.run(
                    ContinuityInput(context=loaded.writer_context, prose=prose)
                )
            ).output
            continuity = ContinuityOutput(
                overall=continuity.overall,
                findings=[*continuity.findings, *secondary.findings],
            )
        written = bundle.writer.model_copy(
            update={
                "output": bundle.writer.output.model_copy(
                    update={
                        "title": loaded.plan.chapter_title,
                        "prose": prose,
                        "word_count": count_text_units(prose),
                    }
                )
            }
        )
        return (
            bundle.model_copy(
                update={
                    "writer": written,
                    "editor": editor_result,
                    "continuity": continuity_result.model_copy(update={"output": continuity}),
                }
            ),
            continuity,
            secondary,
        )


    async def persist_revision(
        self,
        project_id: UUID,
        chapter_number: int,
        content: str,
        *,
        created_by: str,
        change_summary: str,
        overwrite_human: bool = False,
    ) -> ChapterRevision:
        chapter = await self.engine.chapters.get_by_number(project_id, chapter_number)
        repetition_check = scan_chapter_repetition(
            chapter_number=chapter_number,
            content=content,
            chapters=await self.engine.chapters.list(project_id),
        )
        if repetition_check.blocked:
            match = repetition_check.matches[0]
            raise InvalidStateError(
                f"章节内容与第 {match.chapter_number} 章重复，{match.reason}，"
                "请修改后再保存或提交"
            )
        plan = await self.engine.uow.chapter_plans.latest_for_chapter(chapter.id)
        if plan is not None:
            scenes = await self.engine.scene_plans.list(plan.id)
            relevance_check = scan_chapter_relevance(content=content, plan=plan, scenes=scenes)
            if relevance_check.blocked:
                raise InvalidStateError(
                    "章节内容与已批准的章节计划无关，请补齐计划中的角色、地点、冲突或关键信息后再保存"
                )
        existing = await self.engine.revisions.list(chapter.id)
        latest = existing[-1] if existing else None
        if _human_revision(latest) and not overwrite_human and not change_summary.lower().startswith("human"):
            raise InvalidStateError("human revision will not be overwritten by AI")
        return await self.engine.revisions.save_snapshot(
            chapter.id,
            content,
            created_by=created_by,
            change_summary=change_summary,
        )

    async def commit_approved_chapter(
        self,
        project_id: UUID,
        chapter_number: int,
        *,
        confirmed_by: str,
    ) -> CommitResult:
        if not confirmed_by.strip():
            raise InvalidStateError("confirmed_by is required")
        loaded = await self.load(project_id, chapter_number)
        chapter = loaded.chapter
        if not chapter.content.strip():
            raise InvalidStateError("cannot approve an empty chapter")
        if chapter.status is ChapterStatus.DRAFT:
            raise InvalidStateError("review the chapter before approving")
        if chapter.status is ChapterStatus.APPROVED:
            raise InvalidStateError("chapter is already approved")

        repetition_check = scan_chapter_repetition(
            chapter_number=chapter_number,
            content=chapter.content,
            chapters=await self.engine.chapters.list(project_id),
        )
        if repetition_check.blocked:
            match = repetition_check.matches[0]
            raise InvalidStateError(
                f"不能批准：本章与第 {match.chapter_number} 章重复，{match.reason}"
            )
        relevance_check = scan_chapter_relevance(content=chapter.content, plan=loaded.plan, scenes=loaded.scenes)
        if relevance_check.blocked:
            raise InvalidStateError(
                "不能批准：章节内容与已批准的章节计划无关，请先修订正文"
            )

        prose = chapter.content
        plan_agent = plan_to_agent(loaded.plan, loaded.scenes)
        summary_result = await self.workflow.chapter_summary.run(
            ChapterSummaryInput(chapter_number=chapter_number, chapter_plan=plan_agent, prose=prose)
        )
        memory_result = await self.workflow.memory.run(
            MemoryAgentInput(chapter_number=chapter_number, prose=prose, chapter_plan=plan_agent)
        )
        hook_result = await self.workflow.hook.run(
            HookAgentInput(chapter_number=chapter_number, chapter_plan=plan_agent, prose=prose)
        )

        summary = summary_result.output
        # Scene-level extraction is produced during scene generation. Prefer it
        # over a second chapter-level interpretation when available, while
        # retaining the summary agent as a safe fallback for older workflows.
        if memory_result.output.scene_handoffs:
            summary = summary.model_copy(
                update={"scene_handoffs": list(memory_result.output.scene_handoffs)}
            )
        handoff_findings = scan_scene_handoffs(
            prose=prose,
            handoffs=list(summary.scene_handoffs),
            planned_scene_numbers={scene.scene_number for scene in loaded.scenes},
            planned_scene_locations={scene.scene_number: scene.location for scene in loaded.scenes},
            planned_scene_characters={scene.scene_number: set(scene.characters) for scene in loaded.scenes},
            allowed_characters={item.name for item in loaded.characters} | set(loaded.plan.characters),
        )
        hard_handoff_errors = [item for item in handoff_findings if item.severity is ContinuityVerdict.ERROR]
        if hard_handoff_errors:
            details = "; ".join(item.problem for item in hard_handoff_errors[:3])
            raise InvalidStateError(f"不能批准：场景交接记忆校验失败：{details}")
        chapter_memory = ChapterMemory(
            project_id=project_id,
            chapter_number=chapter_number,
            title=summary.title or loaded.plan.chapter_title,
            summary=summary.summary,
            key_events=list(summary.key_events),
            new_facts=list(summary.new_facts),
            character_changes=list(summary.character_changes),
            new_secrets=list(summary.new_secrets),
            resolved_secrets=list(summary.resolved_secrets),
            unresolved_hooks=list(summary.unresolved_hooks),
            location=summary.location or loaded.plan.location,
            characters=list(loaded.plan.characters),
            arc=loaded.arc.summary if loaded.arc else None,
            scene_handoffs=[item.model_dump() for item in summary.scene_handoffs],
        )
        self.memory.add_chapter(chapter_memory, confirmed_by=confirmed_by)

        character_states: list[CharacterMemory] = []
        for name in loaded.plan.characters:
            current = self.memory.store.get_character(project_id, name) or CharacterMemory(
                project_id=project_id, name=name
            )
            changes = [item for item in summary.character_changes if name.split()[0].lower() in item.lower()]
            if not changes:
                changes = list(summary.character_changes[:1])
            experiences = [*current.experiences, *changes, *summary.key_events[:1]]
            knows = list(current.knows)
            does_not_know = list(current.does_not_know)
            for handoff in summary.scene_handoffs:
                for character, facts in handoff.who_knows.items():
                    if character.casefold() == name.casefold():
                        knows.extend(facts)
                for character, facts in handoff.unknown_to.items():
                    if character.casefold() == name.casefold():
                        does_not_know.extend(facts)
            current = current.model_copy(
                update={
                    "experiences": experiences[-12:],
                    "knows": list(dict.fromkeys(knows))[-24:],
                    "does_not_know": list(dict.fromkeys(does_not_know))[-24:],
                    "current_state": changes[0] if changes else f"After chapter {chapter_number}",
                    "relationship_changes": [*current.relationship_changes, *changes][-8:],
                }
            )
            self.memory.upsert_character(current)
            character_states.append(current)

        for candidate in memory_result.output.memories:
            layer = MemoryLayer.CHARACTER if candidate.character_name else MemoryLayer.CHAPTER
            self.memory.write(
                project_id,
                MemoryProposal(
                    layer=layer,
                    suggested_status=EpistemicStatus.TENTATIVE_FACT,
                    memory_type=candidate.memory_type,
                    importance=candidate.importance,
                    content=candidate.content,
                    chapter_number=chapter_number,
                    character_name=candidate.character_name,
                    source="llm",
                ),
                confirmed_by=confirmed_by,
            )

        # Promote scene-level knowledge boundaries to durable fact records. This
        # keeps POV filtering effective after the in-memory pipeline is rebuilt.
        for handoff in summary.scene_handoffs:
            facts_by_character: dict[str, dict[str, list[str]]] = {}
            for character, facts in handoff.who_knows.items():
                for fact in facts:
                    facts_by_character.setdefault(fact, {}).setdefault("known_by", []).append(character)
            for character, facts in handoff.unknown_to.items():
                for fact in facts:
                    facts_by_character.setdefault(fact, {}).setdefault("unknown_to", []).append(character)
            for fact, visibility in facts_by_character.items():
                self.memory.write(
                    project_id,
                    MemoryProposal(
                        layer=MemoryLayer.CHARACTER,
                        suggested_status=EpistemicStatus.TENTATIVE_FACT,
                        memory_type=MemoryType.FACT,
                        importance=Importance.MEDIUM,
                        content=fact,
                        chapter_number=chapter_number,
                        known_by=visibility.get("known_by", []),
                        unknown_to=visibility.get("unknown_to", []),
                        tags=["scene_handoff", f"scene:{handoff.scene_number}"],
                        source="llm",
                    ),
                    confirmed_by=confirmed_by,
                )

        sequence = chapter_number
        timeline = TimelineMemory(
            project_id=project_id,
            sequence=sequence,
            chapter_number=chapter_number,
            in_world_time=f"Chapter {chapter_number}",
            title=loaded.plan.chapter_title,
            description=summary.summary,
            location=loaded.plan.location,
            characters=list(loaded.plan.characters),
            caused_by_sequence=chapter_number - 1 if chapter_number > 1 else None,
        )
        self.memory.add_timeline(timeline)

        hooks: list[Hook] = []
        for proposal in hook_result.output.hooks:
            hook = await self.engine.hooks.create(
                Hook(
                    project_id=project_id,
                    hook_type=proposal.hook_type,
                    description=proposal.description,
                    importance=proposal.importance,
                )
            )
            hook = await self.engine.hooks.plant(hook.id, chapter.id)
            hook = await self.engine.hooks.activate(hook.id)
            hooks.append(hook)
            self.memory.write(
                project_id,
                MemoryProposal(
                    layer=MemoryLayer.CHAPTER,
                    suggested_status=EpistemicStatus.TENTATIVE_FACT,
                    memory_type=MemoryType.HOOK,
                    content=proposal.description,
                    chapter_number=chapter_number,
                    tags=["hook"],
                    source="llm",
                ),
                confirmed_by=confirmed_by,
            )

        foreshadowings: list[Foreshadowing] = []
        for proposal in hook_result.output.foreshadowings:
            item = await self.engine.foreshadowings.create(
                Foreshadowing(
                    project_id=project_id,
                    description=proposal.description,
                    clue_text=proposal.clue_text,
                    status=ForeshadowStatus.PLANNED,
                )
            )
            item = await self.engine.foreshadowings.plant(item.id, chapter.id)
            foreshadowings.append(item)
            self.memory.write(
                project_id,
                MemoryProposal(
                    layer=MemoryLayer.CHAPTER,
                    suggested_status=EpistemicStatus.TENTATIVE_FACT,
                    memory_type=MemoryType.HOOK,
                    content=proposal.description,
                    chapter_number=chapter_number,
                    tags=["foreshadow"],
                    source="llm",
                ),
                confirmed_by=confirmed_by,
            )

        record_chapter(
            self.style_history,
            chapter_number=chapter_number,
            prose=prose,
            location=loaded.plan.location,
            conflict=loaded.plan.conflict,
            watchlist=loaded.style.platform.monitored_phrases,
        )
        approved = await self.engine.chapters.approve(
            project_id,
            chapter_number,
            confirmed_by=confirmed_by,
            commit=False,
        )
        return CommitResult(
            chapter=approved,
            summary=summary,
            memory=memory_result.output,
            hooks=hooks,
            foreshadowings=foreshadowings,
            timeline=timeline,
            character_states=character_states,
            memory_validation={
                "overall": "warning" if handoff_findings else "pass",
                "findings": [item.model_dump(mode="json") for item in handoff_findings],
            },
        )

    def _ensure_global(self, project_id, bible, world, characters, plot) -> None:
        if self.memory.store.get_global(project_id) is not None:
            return
        rules = [rule.description for rule in (world.rules if world else [])]
        self.memory.set_global(
            project_id,
            world=(world.summary if world else bible.premise),
            master_plot=(plot.summary if plot else bible.synopsis or bible.premise),
            core_characters=[item.name for item in characters],
            core_rules=rules or ["Approved World Bible rules are binding."],
            confirmed_by="canon",
        )


def _previous_chapter_context(previous_chapter, previous_memory: ChapterMemory | None = None) -> str:
    if previous_chapter is None or not previous_chapter.content.strip():
        return ""
    handoff_text = ""
    if previous_memory and previous_memory.scene_handoffs:
        handoff_text = "\nScene handoffs:\n" + "\n".join(
            "- Scene {scene}: {event}; changes: {changes}; open questions: {questions}; next: {next_steps}".format(
                scene=item.get("scene_number", "?"),
                event=item.get("what_happened", ""),
                changes="、".join(item.get("character_changes") or []),
                questions="、".join(item.get("open_questions") or []),
                next_steps="、".join(item.get("next_scene_requirements") or []),
            )
            for item in previous_memory.scene_handoffs
        )
        knowledge_text = "\nKnowledge state:\n" + "\n".join(
            f"- {character} knows: {fact}"
            for item in previous_memory.scene_handoffs
            for character, facts in (item.get("who_knows") or {}).items()
            for fact in facts
        ) + "\n" + "\n".join(
            f"- {character} does not know: {fact}"
            for item in previous_memory.scene_handoffs
            for character, facts in (item.get("unknown_to") or {}).items()
            for fact in facts
        )
        handoff_text += knowledge_text if knowledge_text.strip() != "Knowledge state:" else ""
    return (
        f"Chapter {previous_chapter.chapter_number}: {previous_chapter.title}\n"
        f"Ending excerpt:\n{previous_chapter.content[-4000:]}"
        f"{handoff_text}"
    )


def _require_approved_canon(*, bible, world, characters, plot, arc, plan) -> None:
    missing = []
    if world is None:
        missing.append("world bible")
    if plot is None:
        missing.append("master plot")
    if arc is None:
        missing.append("story arc")
    if missing:
        raise InvalidStateError("approved canon is incomplete: " + ", ".join(missing))
    for label, item in (
        ("story bible", bible),
        ("world bible", world),
        ("master plot", plot),
        ("story arc", arc),
        ("chapter plan", plan),
    ):
        if getattr(item, "status", None) is not ApprovalStatus.APPROVED:
            raise InvalidStateError(f"{label} must pass automated approval before generation")
    if not characters or any(
        getattr(item, "status", None) is not ApprovalStatus.APPROVED for item in characters
    ):
        raise InvalidStateError("all chapter characters must pass automated approval before generation")


def _current_arc(arcs: list, chapter_number: int):
    covering = [
        item
        for item in arcs
        if (item.start_chapter_number or 1) <= chapter_number
        and (item.end_chapter_number or 10_000) >= chapter_number
    ]
    if covering:
        return sorted(covering, key=lambda item: item.sequence)[0]
    return arcs[0] if arcs else None


def _beat_warnings(plan: ChapterPlan, style: StyleBundle) -> list[RepetitionWarning]:
    warnings: list[RepetitionWarning] = []
    required = set(style.platform.required_beats)
    if "conflict" in required and not plan.conflict.strip():
        warnings.append(_warn("beats", "conflict", "Chapter plan is missing conflict."))
    if "emotional_beat" in required and not plan.emotional_arc.strip():
        warnings.append(_warn("beats", "emotional_beat", "Chapter plan is missing an emotional beat."))
    if "plot_progress" in required and not plan.new_information.strip():
        warnings.append(_warn("beats", "plot_progress", "Chapter plan is missing plot progress."))
    if style.platform.ending and not plan.cliffhanger.strip():
        warnings.append(_warn("beats", "ending", "Chapter plan is missing a hook or cliffhanger."))
    return warnings


def _word_warnings(prose: str, style: StyleBundle) -> list[RepetitionWarning]:
    count = count_text_units(prose)
    low, high = style.platform.chapter_word_min, style.platform.chapter_word_max
    if count and (count < low or count > high):
        return [
            _warn(
                "length",
                f"{count} words",
                f"Target is {low}-{high} words. This is a warning, not a silent rewrite.",
            )
        ]
    return []


def _warn(category: str, item: str, note: str) -> RepetitionWarning:
    return RepetitionWarning(category=category, item=item, frequency=1, chapters=[], note=note)
