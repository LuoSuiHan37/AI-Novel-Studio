from __future__ import annotations

from novel_engine.models.entities import (
    Chapter,
    ChapterPlan,
    ChapterRevision,
    Character,
    Foreshadowing,
    Hook,
    MasterPlot,
    NovelProject,
    PlotBeat,
    ScenePlan,
    StoryArc,
    StoryBible,
    WorldBible,
    WorldRule,
)
from novel_engine.models.enums import (
    ApprovalStatus,
    ChapterStatus,
    CharacterRole,
    ForeshadowStatus,
    HookStatus,
    HookType,
    Importance,
    IntensityLevel,
    NarrativeTense,
    PipelineStage,
    PointOfView,
    ProjectStatus,
)

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


def _enum(value, cls, default):
    if value is None:
        return default
    if isinstance(value, cls):
        return value
    return cls(value)


def _text(value: str | None, default: str = "") -> str:
    return default if value is None else value


def project_to_domain(row: ProjectRow) -> NovelProject:
    return NovelProject(
        id=row.id,
        title=row.title,
        genre=row.genre,
        tropes=list(row.tropes or []),
        target_platform=row.target_platform,
        language=row.language or "en",
        chapter_count_target=row.chapter_count_target,
        status=_enum(row.status, ProjectStatus, ProjectStatus.PLANNING),
        current_stage=_enum(row.current_stage, PipelineStage, PipelineStage.IDEA),
        extra_metadata=dict(row.extra_metadata or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def apply_project(row: ProjectRow, project: NovelProject) -> None:
    row.title = project.title
    row.genre = project.genre
    row.tropes = list(project.tropes)
    row.target_platform = project.target_platform
    row.language = project.language
    row.chapter_count_target = project.chapter_count_target
    row.status = project.status.value
    row.current_stage = project.current_stage.value
    row.extra_metadata = dict(project.extra_metadata or {})


def story_bible_to_domain(row: StoryBibleRow) -> StoryBible:
    return StoryBible(
        id=row.id,
        project_id=row.project_id,
        premise=_text(row.premise),
        theme=_text(row.theme),
        tone=_text(row.tone),
        narrative_style=_text(row.narrative_style),
        pov=_enum(row.pov, PointOfView, PointOfView.THIRD_LIMITED),
        tense=_enum(row.tense, NarrativeTense, NarrativeTense.PAST),
        target_word_count=row.target_word_count or 50_000,
        chapter_word_count=row.chapter_word_count or 2_500,
        romance_level=_enum(row.romance_level, IntensityLevel, IntensityLevel.HIGH),
        violence_level=_enum(row.violence_level, IntensityLevel, IntensityLevel.MEDIUM),
        heat_level=_enum(row.heat_level, IntensityLevel, IntensityLevel.MEDIUM),
        tropes=list(row.tropes or []),
        logline=row.logline,
        synopsis=row.synopsis,
        extra_metadata=dict(row.extra_metadata or {}),
        status=_enum(row.status, ApprovalStatus, ApprovalStatus.DRAFT),
        updated_at=row.updated_at,
    )


def apply_story_bible(row: StoryBibleRow, bible: StoryBible) -> None:
    row.premise = bible.premise
    row.theme = bible.theme
    row.tone = bible.tone
    row.narrative_style = bible.narrative_style
    row.pov = bible.pov.value
    row.tense = bible.tense.value
    row.target_word_count = bible.target_word_count
    row.chapter_word_count = bible.chapter_word_count
    row.romance_level = bible.romance_level.value
    row.violence_level = bible.violence_level.value
    row.heat_level = bible.heat_level.value
    row.tropes = list(bible.tropes)
    row.logline = bible.logline
    row.synopsis = bible.synopsis
    row.extra_metadata = dict(bible.extra_metadata or {})
    row.status = bible.status.value


def world_bible_to_domain(row: WorldBibleRow) -> WorldBible:
    return WorldBible(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        summary=_text(row.summary),
        geography=row.geography,
        factions=list(row.factions or []),
        rules=[world_rule_to_domain(item) for item in (row.rules or [])],
        status=_enum(row.status, ApprovalStatus, ApprovalStatus.DRAFT),
        updated_at=row.updated_at,
    )


def world_rule_to_domain(row: WorldRuleRow) -> WorldRule:
    return WorldRule(
        id=row.id,
        world_bible_id=row.world_bible_id,
        name=row.name,
        category=row.category,
        description=row.description,
        is_hard_constraint=row.is_hard_constraint,
    )


def apply_world_bible(row: WorldBibleRow, bible: WorldBible) -> None:
    row.name = bible.name or "Untitled World"
    row.summary = bible.summary
    row.geography = bible.geography
    row.factions = list(bible.factions)
    row.status = bible.status.value


def character_to_domain(row: CharacterRow) -> Character:
    background = row.background or row.backstory or ""
    return Character(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        aliases=list(row.aliases or []),
        role=_enum(row.role, CharacterRole, CharacterRole.SUPPORTING),
        personality=_text(row.personality),
        background=background,
        goal=_text(row.goal or row.goals),
        motivation=_text(row.motivation),
        fear=_text(row.fear),
        secret=_text(row.secret),
        strength=_text(row.strength),
        weakness=_text(row.weakness),
        internal_conflict=_text(row.internal_conflict),
        external_conflict=_text(row.external_conflict),
        speech_style=_text(row.speech_style),
        character_arc=_text(row.character_arc),
        species=row.species,
        rank=row.rank,
        tropes=list(row.tropes or []),
        status=_enum(row.status, ApprovalStatus, ApprovalStatus.DRAFT),
        updated_at=row.updated_at,
    )


def apply_character(row: CharacterRow, character: Character) -> None:
    row.name = character.name
    row.aliases = list(character.aliases)
    row.role = character.role.value
    row.personality = character.personality
    row.background = character.background
    row.backstory = character.background
    row.goal = character.goal
    row.goals = character.goal
    row.motivation = character.motivation
    row.fear = character.fear
    row.secret = character.secret
    row.strength = character.strength
    row.weakness = character.weakness
    row.internal_conflict = character.internal_conflict
    row.external_conflict = character.external_conflict
    row.speech_style = character.speech_style
    row.character_arc = character.character_arc
    row.species = character.species
    row.rank = character.rank
    row.tropes = list(character.tropes)
    row.status = character.status.value


def plot_to_domain(row: MasterPlotRow) -> MasterPlot:
    beats: list[PlotBeat] = []
    for item in row.beats or []:
        if isinstance(item, dict):
            beats.append(PlotBeat.model_validate(item))
    return MasterPlot(
        id=row.id,
        project_id=row.project_id,
        title=row.title,
        structure=row.structure,
        summary=_text(row.summary),
        beats=beats,
        is_active=row.is_active,
        status=_enum(row.status, ApprovalStatus, ApprovalStatus.DRAFT),
        updated_at=row.updated_at,
    )


def apply_plot(row: MasterPlotRow, plot: MasterPlot) -> None:
    row.title = plot.title
    row.structure = plot.structure
    row.summary = plot.summary
    row.beats = [item.model_dump() for item in plot.beats]
    row.is_active = plot.is_active
    row.status = plot.status.value


def arc_to_domain(row: StoryArcRow) -> StoryArc:
    return StoryArc(
        id=row.id,
        project_id=row.project_id,
        master_plot_id=row.master_plot_id,
        title=row.title,
        arc_type=row.arc_type,
        sequence=row.sequence,
        summary=_text(row.summary),
        start_chapter_number=row.start_chapter_number,
        end_chapter_number=row.end_chapter_number,
        status=_enum(row.status, ApprovalStatus, ApprovalStatus.DRAFT),
        updated_at=row.updated_at,
    )


def apply_arc(row: StoryArcRow, arc: StoryArc) -> None:
    row.master_plot_id = arc.master_plot_id
    row.title = arc.title
    row.arc_type = arc.arc_type
    row.sequence = arc.sequence
    row.summary = arc.summary
    row.start_chapter_number = arc.start_chapter_number
    row.end_chapter_number = arc.end_chapter_number
    row.status = arc.status.value


def chapter_to_domain(row: ChapterRow) -> Chapter:
    return Chapter(
        id=row.id,
        project_id=row.project_id,
        story_arc_id=row.story_arc_id,
        chapter_number=row.chapter_number,
        title=row.title,
        status=_enum(row.status, ChapterStatus, ChapterStatus.DRAFT),
        content=row.content or "",
        word_count=row.word_count or 0,
        current_revision_id=row.current_revision_id,
        extra_metadata=dict(row.extra_metadata or {}),
    )


def apply_chapter(row: ChapterRow, chapter: Chapter) -> None:
    row.story_arc_id = chapter.story_arc_id
    row.chapter_number = chapter.chapter_number
    row.title = chapter.title
    row.status = chapter.status.value
    row.content = chapter.content
    row.word_count = chapter.word_count
    row.current_revision_id = chapter.current_revision_id
    row.extra_metadata = dict(chapter.extra_metadata or {})


def plan_to_domain(row: ChapterPlanRow) -> ChapterPlan:
    return ChapterPlan(
        id=row.id,
        project_id=row.project_id,
        chapter_id=row.chapter_id,
        version=row.version,
        chapter_number=row.chapter_number or 1,
        chapter_title=_text(row.chapter_title),
        pov=_text(row.pov),
        location=_text(row.location),
        characters=list(row.characters or []),
        chapter_goal=_text(row.chapter_goal or row.goal),
        conflict=_text(row.conflict),
        emotional_arc=_text(row.emotional_arc or row.emotional_beat),
        new_information=_text(row.new_information),
        reveal=_text(row.reveal),
        foreshadowing=_text(row.foreshadowing),
        setup=_text(row.setup),
        payoff=_text(row.payoff),
        cliffhanger=_text(row.cliffhanger or row.hook_plan),
        target_word_count=int((row.extra_metadata or {}).get("target_word_count", 0) or 0),
        target_word_min=int((row.extra_metadata or {}).get("target_word_min", 0) or 0),
        target_word_max=int((row.extra_metadata or {}).get("target_word_max", 0) or 0),
        status=_enum(row.status, ApprovalStatus, ApprovalStatus.DRAFT),
        updated_at=row.updated_at,
    )


def apply_plan(row: ChapterPlanRow, plan: ChapterPlan) -> None:
    row.project_id = plan.project_id
    row.chapter_id = plan.chapter_id
    row.version = plan.version
    row.chapter_number = plan.chapter_number
    row.chapter_title = plan.chapter_title
    row.pov = plan.pov
    row.location = plan.location
    row.characters = list(plan.characters)
    row.chapter_goal = plan.chapter_goal
    row.goal = plan.chapter_goal
    row.conflict = plan.conflict
    row.emotional_arc = plan.emotional_arc
    row.emotional_beat = plan.emotional_arc
    row.new_information = plan.new_information
    row.reveal = plan.reveal
    row.foreshadowing = plan.foreshadowing
    row.setup = plan.setup
    row.payoff = plan.payoff
    row.cliffhanger = plan.cliffhanger
    row.extra_metadata = {
        **dict(row.extra_metadata or {}),
        "target_word_count": plan.target_word_count,
        "target_word_min": plan.target_word_min,
        "target_word_max": plan.target_word_max,
    }
    row.status = plan.status.value


def scene_to_domain(row: ScenePlanRow) -> ScenePlan:
    return ScenePlan(
        id=row.id,
        chapter_plan_id=row.chapter_plan_id,
        scene_number=row.scene_number,
        location=_text(row.location),
        characters=list(row.characters or []),
        goal=_text(row.goal),
        conflict=_text(row.conflict),
        turning_point=_text(row.turning_point),
        dialogue_goal=_text(row.dialogue_goal),
        emotion=_text(row.emotion),
        information_revealed=_text(row.information_revealed),
        ending=_text(row.ending or row.outcome),
        target_word_count=int((row.extra_metadata or {}).get("target_word_count", 0) or 0),
        target_word_min=int((row.extra_metadata or {}).get("target_word_min", 0) or 0),
        target_word_max=int((row.extra_metadata or {}).get("target_word_max", 0) or 0),
    )


def apply_scene(row: ScenePlanRow, scene: ScenePlan) -> None:
    row.chapter_plan_id = scene.chapter_plan_id
    row.scene_number = scene.scene_number
    row.location = scene.location
    row.characters = list(scene.characters)
    row.goal = scene.goal
    row.conflict = scene.conflict
    row.turning_point = scene.turning_point
    row.dialogue_goal = scene.dialogue_goal
    row.emotion = scene.emotion
    row.information_revealed = scene.information_revealed
    row.ending = scene.ending
    row.extra_metadata = {
        **dict(row.extra_metadata or {}),
        "target_word_count": scene.target_word_count,
        "target_word_min": scene.target_word_min,
        "target_word_max": scene.target_word_max,
    }
    row.outcome = scene.ending


def revision_to_domain(row: ChapterRevisionRow) -> ChapterRevision:
    return ChapterRevision(
        id=row.id,
        chapter_id=row.chapter_id,
        revision_number=row.revision_number,
        content=row.content,
        word_count=row.word_count,
        change_summary=row.change_summary,
        restored_from_revision_id=row.restored_from_revision_id,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def apply_revision(row: ChapterRevisionRow, revision: ChapterRevision) -> None:
    row.chapter_id = revision.chapter_id
    row.revision_number = revision.revision_number
    row.content = revision.content
    row.word_count = revision.word_count
    row.change_summary = revision.change_summary
    row.restored_from_revision_id = revision.restored_from_revision_id
    row.created_by = revision.created_by


def hook_to_domain(row: HookRow) -> Hook:
    return Hook(
        id=row.id,
        project_id=row.project_id,
        hook_type=_enum(row.hook_type, HookType, HookType.CLIFFHANGER),
        setup_chapter_id=row.setup_chapter_id,
        resolved_chapter_id=row.resolved_chapter_id,
        status=_enum(row.status, HookStatus, HookStatus.PLANNED),
        importance=_enum(row.importance, Importance, Importance.HIGH),
        description=row.description,
    )


def apply_hook(row: HookRow, hook: Hook) -> None:
    row.hook_type = hook.hook_type.value
    row.setup_chapter_id = hook.setup_chapter_id
    row.resolved_chapter_id = hook.resolved_chapter_id
    row.status = hook.status.value
    row.importance = hook.importance.value
    row.description = hook.description


def foreshadow_to_domain(row: ForeshadowingRow) -> Foreshadowing:
    return Foreshadowing(
        id=row.id,
        project_id=row.project_id,
        setup_chapter_id=row.setup_chapter_id,
        expected_payoff_chapter_id=row.expected_payoff_chapter_id,
        actual_payoff_chapter_id=row.actual_payoff_chapter_id,
        status=_enum(row.status, ForeshadowStatus, ForeshadowStatus.PLANNED),
        description=row.description,
        clue_text=row.clue_text,
    )


def apply_foreshadow(row: ForeshadowingRow, item: Foreshadowing) -> None:
    row.setup_chapter_id = item.setup_chapter_id
    row.expected_payoff_chapter_id = item.expected_payoff_chapter_id
    row.actual_payoff_chapter_id = item.actual_payoff_chapter_id
    row.status = item.status.value
    row.description = item.description
    row.clue_text = item.clue_text
