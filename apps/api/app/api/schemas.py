from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from novel_engine.models.entities import (
    Chapter,
    ChapterPlan,
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
    IntensityLevel,
    NarrativeTense,
    PipelineStage,
    PointOfView,
    ProjectStatus,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(ApiModel):
    title: str
    genre: str = "werewolf_romance"
    tropes: list[str] = Field(default_factory=list)
    target_platform: str | None = "alphanovel"
    language: str = "en"
    chapter_count_target: int | None = Field(default=120, ge=1, le=5000)
    premise: str | None = None
    theme: str | None = None
    tone: str | None = None
    logline: str | None = None
    synopsis: str | None = None


class CreationDraftSave(ApiModel):
    """The resumable state of the multi-step book creation wizard."""

    state: dict = Field(default_factory=dict)


class ProjectTitleSuggest(ApiModel):
    genre: str = "werewolf_romance"
    target_platform: str = "alphanovel"
    tropes: list[str] = Field(default_factory=list)
    brief: str = ""
    language: str = "en"
    research_profile: dict | None = None
    research_binding: "ResearchBinding | None" = None
    research_project_id: uuid.UUID | None = None


class ResearchBinding(ApiModel):
    """Stable provenance for creative output derived from reference research."""

    session_id: str
    source_ids: list[str] = Field(min_length=1)
    profile_artifact_id: str = "profile"
    profile_version: int = Field(default=1, ge=1)


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    genre: str | None = None
    tropes: list[str] | None = None
    target_platform: str | None = None
    language: str | None = None
    chapter_count_target: int | None = Field(default=None, ge=1, le=5000)
    status: ProjectStatus | None = None
    premise: str | None = None
    theme: str | None = None
    tone: str | None = None
    logline: str | None = None
    synopsis: str | None = None
    creative_profile: dict | None = None


class CreationPitch(ApiModel):
    premise: str
    theme: str
    logline: str
    synopsis: str
    reading_tags: list[str] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)
    protagonist_names: list[str] = Field(default_factory=list)
    work_tags: dict[str, list[str]] = Field(default_factory=dict)
    research_binding: ResearchBinding


class ProjectFinalizeCreation(ApiModel):
    title: str
    genre: str
    language: str = "en"
    target_platform: str | None = "alphanovel"
    chapter_count_target: int = Field(default=120, ge=1, le=5000)
    target_reader: str = "female"
    pitch: CreationPitch
    research_binding: ResearchBinding
    framework_proposal: dict
    framework_confirmed: bool = False
    confirmed_by: str


class StoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    premise: str
    theme: str
    tone: str = "dark romantic"
    narrative_style: str = "close third serial"
    pov: PointOfView = PointOfView.THIRD_LIMITED
    tense: NarrativeTense = NarrativeTense.PAST
    target_word_count: int = 80_000
    chapter_word_count: int = 2_500
    romance_level: IntensityLevel = IntensityLevel.HIGH
    violence_level: IntensityLevel = IntensityLevel.MEDIUM
    heat_level: IntensityLevel = IntensityLevel.MEDIUM
    tropes: list[str] = Field(default_factory=list)
    logline: str | None = None
    synopsis: str | None = None
    target_reader: str = "female"
    reading_tags: list[str] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)
    protagonist_names: list[str] = Field(default_factory=list)
    work_tags: dict[str, list[str]] = Field(default_factory=dict)


class CharacterCreate(ApiModel):
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


class CharacterPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    aliases: list[str] | None = None
    role: CharacterRole | None = None
    personality: str | None = None
    background: str | None = None
    goal: str | None = None
    motivation: str | None = None
    fear: str | None = None
    secret: str | None = None
    strength: str | None = None
    weakness: str | None = None
    internal_conflict: str | None = None
    external_conflict: str | None = None
    speech_style: str | None = None
    character_arc: str | None = None
    species: str | None = None
    rank: str | None = None
    tropes: list[str] | None = None


class WorldRuleIn(ApiModel):
    name: str
    category: str = "general"
    description: str
    is_hard_constraint: bool = True


class WorldPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    summary: str
    geography: str | None = None
    factions: list[str] = Field(default_factory=list)
    rules: list[WorldRuleIn] = Field(default_factory=list)


class BeatIn(ApiModel):
    name: str
    description: str
    chapter_hint: int | None = None


class PlotPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    structure: str = "three_act"
    summary: str
    beats: list[BeatIn]
    is_active: bool = True


class ArcCreate(ApiModel):
    title: str
    master_plot_id: uuid.UUID | None = None
    arc_type: str = "main"
    sequence: int
    summary: str
    start_chapter_number: int | None = None
    end_chapter_number: int | None = None


class ArchitectureApply(ApiModel):
    """Human-confirmed book architecture returned by the outline agent."""

    title: str
    structure: str = "three_act"
    summary: str
    beats: list[BeatIn]
    arcs: list[ArcCreate] = Field(default_factory=list)


class ArcPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    master_plot_id: uuid.UUID | None = None
    arc_type: str | None = None
    sequence: int | None = None
    summary: str | None = None
    start_chapter_number: int | None = None
    end_chapter_number: int | None = None


class SceneIn(ApiModel):
    scene_number: int
    location: str
    characters: list[str]
    goal: str
    conflict: str
    turning_point: str
    dialogue_goal: str
    emotion: str
    information_revealed: str
    ending: str
    # These fields are produced by the chapter-planner agent and are used as
    # writing constraints. Keep them when persisting the plan instead of
    # rejecting the otherwise valid AI response as extra input.
    protagonist_want: str | None = None
    active_pressure: str | None = None
    choice_and_cost: str | None = None
    irreversible_change: str | None = None
    environment_pressure: str | None = None
    target_word_count: int | None = None
    target_word_min: int | None = None
    target_word_max: int | None = None


class ChapterPlanCreate(ApiModel):
    chapter_number: int
    chapter_title: str
    pov: str
    location: str
    characters: list[str]
    chapter_goal: str
    conflict: str
    emotional_arc: str
    new_information: str
    reveal: str
    foreshadowing: str
    setup: str
    payoff: str
    cliffhanger: str
    scenes: list[SceneIn] = Field(default_factory=list)
    target_word_count: int | None = None
    target_word_min: int | None = None
    target_word_max: int | None = None


class ChapterPlanSuggest(ApiModel):
    chapter_number: int = Field(ge=1)


class ChapterPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    story_arc_id: uuid.UUID | None = None
    content: str | None = None
    audit: dict | None = None


class GenerateBody(ApiModel):
    human_notes: str | None = None
    persist: bool = False
    generate_scenes: bool = False
    overwrite_human: bool = False


class ProposeEditBody(ApiModel):
    instruction: str
    source_prose: str
    persist: bool = False


class ConfirmBody(ApiModel):
    confirmed_by: str | None = None
    note: str | None = None


class LLMSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "default"
    provider: str
    model: str
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = 4096
    is_default: bool = True
    api_key_env_name: str | None = None


class LLMSettingsOut(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    provider: str
    model: str
    base_url: str | None
    temperature: float
    max_tokens: int | None
    is_default: bool
    api_key_env_name: str | None


class MemoryItemOut(ApiModel):
    id: uuid.UUID
    layer: str
    epistemic_status: str
    memory_type: str
    importance: str
    content: str
    chapter_number: int | None = None
    location: str | None = None
    known_by: list[str] = Field(default_factory=list)
    unknown_to: list[str] = Field(default_factory=list)
    extra_metadata: dict = Field(default_factory=dict)


class TimelineItemOut(ApiModel):
    id: uuid.UUID
    sequence: int
    in_world_time: str | None
    title: str
    description: str | None
    location: str | None


class ActorOut(ApiModel):
    id: str
    is_authenticated: bool
    auth: str = "reserved"


class ResearchSourceCreate(ApiModel):
    title: str
    author: str | None = None
    source_type: str = "markdown"
    path: str | None = None
    url: str | None = None
    chapter_count: int = 0
    word_count: int = 0
    selected_dimensions: list[str] = Field(default_factory=lambda: [
        "plot", "characters", "style", "narrative", "dialogue", "pacing", "continuity"
    ])


class ResearchSourceUpload(ApiModel):
    title: str | None = None
    filename: str
    content: str


class ResearchStageUpdate(ApiModel):
    output: str = ""
    status: str = "done"
    execute: bool = False


class ResearchSessionOut(ApiModel):
    session_id: str = ""
    status: str
    progress: int
    stages: list[dict]
    sources: list[dict]
    artifacts: list[dict]
    injection_approved_by: str | None = None
    injection_note: str | None = None
    creative_profile: dict | None = None
    active_task: dict | None = None
