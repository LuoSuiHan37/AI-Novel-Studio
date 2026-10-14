from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NovelProject(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    title: str
    genre: str = "werewolf_romance"
    tropes: list[str] = Field(default_factory=list)
    target_platform: str | None = None
    language: str = "en"
    chapter_count_target: int | None = Field(default=None, ge=1)
    status: ProjectStatus = ProjectStatus.PLANNING
    current_stage: PipelineStage = PipelineStage.IDEA
    extra_metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StoryBible(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    premise: str
    theme: str
    tone: str
    narrative_style: str
    pov: PointOfView = PointOfView.THIRD_LIMITED
    tense: NarrativeTense = NarrativeTense.PAST
    target_word_count: int
    chapter_word_count: int
    romance_level: IntensityLevel = IntensityLevel.HIGH
    violence_level: IntensityLevel = IntensityLevel.MEDIUM
    heat_level: IntensityLevel = IntensityLevel.MEDIUM
    tropes: list[str] = Field(default_factory=list)
    logline: str | None = None
    synopsis: str | None = None
    extra_metadata: dict = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.DRAFT
    updated_at: datetime = Field(default_factory=utcnow)


class WorldRule(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    world_bible_id: uuid.UUID = Field(default_factory=new_id)
    name: str
    category: str = "general"
    description: str
    is_hard_constraint: bool = True


class WorldBible(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    name: str
    summary: str
    geography: str | None = None
    factions: list[str] = Field(default_factory=list)
    rules: list[WorldRule] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.DRAFT
    updated_at: datetime = Field(default_factory=utcnow)


class Character(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: CharacterRole = CharacterRole.SUPPORTING
    personality: str
    background: str
    goal: str
    motivation: str
    fear: str
    secret: str
    strength: str
    weakness: str
    internal_conflict: str
    external_conflict: str
    speech_style: str
    character_arc: str
    species: str | None = "werewolf"
    rank: str | None = None
    tropes: list[str] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.DRAFT
    updated_at: datetime = Field(default_factory=utcnow)


class PlotBeat(DomainModel):
    name: str
    description: str
    chapter_hint: int | None = None


class MasterPlot(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    title: str
    structure: str = "three_act"
    summary: str
    beats: list[PlotBeat] = Field(default_factory=list)
    is_active: bool = True
    status: ApprovalStatus = ApprovalStatus.DRAFT
    updated_at: datetime = Field(default_factory=utcnow)


class StoryArc(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    master_plot_id: uuid.UUID
    title: str
    arc_type: str = "main"
    sequence: int
    summary: str
    start_chapter_number: int | None = None
    end_chapter_number: int | None = None
    status: ApprovalStatus = ApprovalStatus.DRAFT
    updated_at: datetime = Field(default_factory=utcnow)


class Chapter(DomainModel):
    """Placeholder chapter row. Prose is stored only when a human/editor supplies it."""

    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    story_arc_id: uuid.UUID | None = None
    chapter_number: int
    title: str
    status: ChapterStatus = ChapterStatus.DRAFT
    content: str = ""
    word_count: int = 0
    current_revision_id: uuid.UUID | None = None
    extra_metadata: dict = Field(default_factory=dict)


class ChapterPlan(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    chapter_id: uuid.UUID = Field(default_factory=new_id)
    version: int = 1
    chapter_number: int
    chapter_title: str
    pov: str
    location: str
    characters: list[str] = Field(default_factory=list)
    chapter_goal: str
    conflict: str
    emotional_arc: str
    new_information: str
    reveal: str
    foreshadowing: str
    setup: str
    payoff: str
    cliffhanger: str
    target_word_count: int = 0
    target_word_min: int = 0
    target_word_max: int = 0
    status: ApprovalStatus = ApprovalStatus.DRAFT
    updated_at: datetime = Field(default_factory=utcnow)


class ScenePlan(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    chapter_plan_id: uuid.UUID
    scene_number: int
    location: str
    characters: list[str] = Field(default_factory=list)
    goal: str
    conflict: str
    turning_point: str
    dialogue_goal: str
    emotion: str
    information_revealed: str
    ending: str
    target_word_count: int = 0
    target_word_min: int = 0
    target_word_max: int = 0


class ChapterRevision(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    chapter_id: uuid.UUID
    revision_number: int
    content: str
    word_count: int = 0
    change_summary: str | None = None
    restored_from_revision_id: uuid.UUID | None = None
    created_by: str = "human"
    created_at: datetime = Field(default_factory=utcnow)


class Hook(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    hook_type: HookType = HookType.CLIFFHANGER
    setup_chapter_id: uuid.UUID | None = None
    resolved_chapter_id: uuid.UUID | None = None
    status: HookStatus = HookStatus.PLANNED
    importance: Importance = Importance.HIGH
    description: str


class Foreshadowing(DomainModel):
    id: uuid.UUID = Field(default_factory=new_id)
    project_id: uuid.UUID
    setup_chapter_id: uuid.UUID | None = None
    expected_payoff_chapter_id: uuid.UUID | None = None
    actual_payoff_chapter_id: uuid.UUID | None = None
    status: ForeshadowStatus = ForeshadowStatus.PLANNED
    description: str
    clue_text: str | None = None


class ApprovalAction(DomainModel):
    confirmed_by: str
    note: str | None = None


def touch(model: DomainModel) -> None:
    if hasattr(model, "updated_at"):
        setattr(model, "updated_at", utcnow())
