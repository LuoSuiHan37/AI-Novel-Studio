from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_engine.models.enums import (
    CharacterRole,
    ContinuityVerdict,
    HookType,
    Importance,
    IntensityLevel,
    MemoryType,
    NarrativeTense,
    PointOfView,
)


class AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdeaInput(AgentModel):
    tropes: list[str]
    genre: str = "werewolf_romance"
    platform: str = "alphanovel"
    brief: str
    heat_level: IntensityLevel = IntensityLevel.MEDIUM
    language: str = "en"


class IdeaOutput(AgentModel):
    working_title: str
    logline: str
    premise: str
    theme: str = ""
    synopsis: str = ""
    tropes: list[str]
    series_hooks: list[str]
    risks: list[str]
    reading_tags: list[str] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)
    protagonist_names: list[str] = Field(default_factory=list)


class StoryArchitectInput(AgentModel):
    idea: IdeaOutput
    target_word_count: int
    chapter_word_count: int
    tropes: list[str]


class StoryArchitectOutput(AgentModel):
    premise: str
    theme: str
    tone: str
    narrative_style: str
    pov: PointOfView
    tense: NarrativeTense
    romance_level: IntensityLevel
    violence_level: IntensityLevel
    heat_level: IntensityLevel
    logline: str
    synopsis: str
    core_question: str = ""
    reader_promise: str = ""
    ending_direction: str = ""
    forbidden_treatments: list[str] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)


class CharacterAgentInput(AgentModel):
    story_bible: StoryArchitectOutput
    role: CharacterRole
    name_hint: str | None = None
    tropes: list[str]


class CharacterAgentOutput(AgentModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: CharacterRole
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
    tropes: list[str]
    contradictions: list[str] = Field(default_factory=list)
    current_want: str = ""
    misbelief: str = ""
    cost_of_change: str = ""


class WorldAgentInput(AgentModel):
    story_bible: StoryArchitectOutput
    tropes: list[str]


class WorldRuleDraft(AgentModel):
    name: str
    category: str
    description: str
    is_hard_constraint: bool = True


class WorldAgentOutput(AgentModel):
    name: str
    summary: str
    geography: str
    factions: list[str]
    rules: list[WorldRuleDraft]


class OutlineBeat(AgentModel):
    name: str
    description: str
    chapter_hint: int | None = None


class OutlineArc(AgentModel):
    title: str
    sequence: int
    summary: str
    start_chapter_number: int
    end_chapter_number: int


class OutlineInput(AgentModel):
    story_bible: StoryArchitectOutput
    characters: list[CharacterAgentOutput]
    world: WorldAgentOutput
    target_chapter_count: int


class OutlineOutput(AgentModel):
    title: str
    structure: str
    summary: str
    beats: list[OutlineBeat]
    arcs: list[OutlineArc]


class ChapterPlannerInput(AgentModel):
    story_bible: StoryArchitectOutput
    outline: OutlineOutput
    characters: list[CharacterAgentOutput]
    chapter_number: int
    previous_chapter_summary: str | None = None
    style_guide: str = ""
    current_arc: str = ""
    world_rules: list[str] = Field(default_factory=list)
    open_hooks: list[str] = Field(default_factory=list)
    language: str = "en"
    creative_profile: dict = Field(default_factory=dict)


class SceneDraft(AgentModel):
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
    protagonist_want: str = ""
    active_pressure: str = ""
    choice_and_cost: str = ""
    irreversible_change: str = ""
    environment_pressure: str = ""
    target_word_count: int = 0
    target_word_min: int = 0
    target_word_max: int = 0


class ChapterPlannerOutput(AgentModel):
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
    scenes: list[SceneDraft]
    target_word_count: int = 0
    target_word_min: int = 0
    target_word_max: int = 0


class MemorySnippet(AgentModel):
    memory_type: MemoryType
    importance: Importance
    content: str


class WriterContext(AgentModel):
    """Frozen canon snapshot. WriterAgent must not invent replacements for these facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    story_bible: StoryArchitectOutput
    world_rules: list[str]
    characters: list[CharacterAgentOutput]
    chapter_plan: ChapterPlannerOutput
    open_hooks: list[str] = Field(default_factory=list)
    memories: list[MemorySnippet] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    forbidden_knowledge: dict[str, list[str]] = Field(default_factory=dict)
    current_arc: str = ""
    style_guide: str = ""
    anti_repetition_notes: tuple[str, ...] = ()
    memory_brief: str = ""
    previous_chapter_summary: str = ""
    language: str = "en"
    creative_profile: dict = Field(default_factory=dict)
    chapter_word_min: int = 1500
    chapter_word_max: int = 2500
    novel_constitution: dict = Field(default_factory=dict)
    environment_bible: dict = Field(default_factory=dict)
    relationship_ledger: list[dict] = Field(default_factory=list)


class WriterInput(AgentModel):
    context: WriterContext
    human_notes: str | None = None


class WriterOutput(AgentModel):
    title: str
    prose: str
    word_count: int
    used_character_names: list[str]
    planted_hooks: list[str]


class ReviseInput(AgentModel):
    instruction: str
    source_prose: str


class ReviseOutput(AgentModel):
    prose: str
    change_summary: str


class DimensionNote(AgentModel):
    score: int = Field(ge=1, le=10)
    notes: str


class EditorInput(AgentModel):
    context: WriterContext
    prose: str


class EditorOutput(AgentModel):
    overall_notes: str
    needs_human_review: bool
    pacing: DimensionNote
    dialogue: DimensionNote
    emotion: DimensionNote
    character_voice: DimensionNote
    show_dont_tell: DimensionNote
    repetition: DimensionNote
    grammar: DimensionNote
    hook_strength: DimensionNote
    romantic_tension: DimensionNote
    plot_progress: DimensionNote


class CommercialReviewInput(AgentModel):
    context: WriterContext
    prose: str


class CommercialReviewOutput(AgentModel):
    reader_pressure_score: int = Field(ge=1, le=10)
    reader_promise_score: int = Field(ge=1, le=10)
    rhythm_score: int = Field(ge=1, le=10)
    ai_style_risk_score: int = Field(ge=1, le=10)
    needs_human_review: bool
    findings: list[str] = Field(default_factory=list)
    repair_priorities: list[str] = Field(default_factory=list)


class ContinuityInput(AgentModel):
    context: WriterContext
    prose: str


class ContinuityFinding(AgentModel):
    severity: ContinuityVerdict
    category: str
    problem: str
    evidence: str
    recommendation: str


class ContinuityOutput(AgentModel):
    overall: ContinuityVerdict
    findings: list[ContinuityFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def _rollup(self) -> ContinuityOutput:
        if any(item.severity is ContinuityVerdict.ERROR for item in self.findings):
            self.overall = ContinuityVerdict.ERROR
        elif any(item.severity is ContinuityVerdict.WARNING for item in self.findings):
            if self.overall is ContinuityVerdict.PASS:
                self.overall = ContinuityVerdict.WARNING
        return self


class MemoryAgentInput(AgentModel):
    chapter_number: int
    prose: str
    chapter_plan: ChapterPlannerOutput


class MemoryCandidate(AgentModel):
    memory_type: MemoryType
    importance: Importance
    content: str
    character_name: str | None = None
    known_by: list[str] = Field(default_factory=list)
    unknown_to: list[str] = Field(default_factory=list)
    source_excerpt: str = ""


class SceneHandoff(AgentModel):
    """The accepted state transition a later scene/chapter must inherit."""

    scene_number: int
    location: str = ""
    time_marker: str = ""
    what_happened: str
    character_changes: list[str] = Field(default_factory=list)
    new_information: list[str] = Field(default_factory=list)
    relationship_changes: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_scene_requirements: list[str] = Field(default_factory=list)
    who_knows: dict[str, list[str]] = Field(default_factory=dict)
    unknown_to: dict[str, list[str]] = Field(default_factory=dict)
    source_excerpt: str = ""


class MemoryAgentOutput(AgentModel):
    memories: list[MemoryCandidate]
    scene_handoffs: list[SceneHandoff] = Field(default_factory=list)


class HookAgentInput(AgentModel):
    chapter_number: int
    chapter_plan: ChapterPlannerOutput
    prose: str | None = None


class HookProposal(AgentModel):
    hook_type: HookType
    description: str
    importance: Importance
    setup_chapter_number: int | None = None


class ForeshadowProposal(AgentModel):
    description: str
    clue_text: str
    expected_payoff_chapter_number: int | None = None


class HookAgentOutput(AgentModel):
    hooks: list[HookProposal]
    foreshadowings: list[ForeshadowProposal]


class ChapterSummaryInput(AgentModel):
    chapter_number: int
    chapter_plan: ChapterPlannerOutput
    prose: str


class ChapterSummaryOutput(AgentModel):
    title: str
    summary: str
    key_events: list[str] = Field(default_factory=list)
    new_facts: list[str] = Field(default_factory=list)
    character_changes: list[str] = Field(default_factory=list)
    new_secrets: list[str] = Field(default_factory=list)
    resolved_secrets: list[str] = Field(default_factory=list)
    unresolved_hooks: list[str] = Field(default_factory=list)
    location: str | None = None
    scene_handoffs: list[SceneHandoff] = Field(default_factory=list)
