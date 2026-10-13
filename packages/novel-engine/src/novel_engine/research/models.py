from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DistillationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str
    finding: str
    reusable_rule: str
    evidence: str
    locator: str


class SourceDistillation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    premise: str
    opening_promise: str
    structural_summary: str
    observations: list[DistillationObservation] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)


class SynthesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shared_patterns: list[str] = Field(default_factory=list)
    divergent_patterns: list[str] = Field(default_factory=list)
    structure_controls: list[str] = Field(default_factory=list)
    pacing_controls: list[str] = Field(default_factory=list)
    blurb_controls: list[str] = Field(default_factory=list)
    style_controls: list[str] = Field(default_factory=list)
    originality_guardrails: list[str] = Field(default_factory=list)
    evidence_map: list[str] = Field(default_factory=list)


class CreativeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positioning: str
    title_patterns: list[str] = Field(default_factory=list)
    blurb_formula: list[str] = Field(default_factory=list)
    opening_requirements: list[str] = Field(default_factory=list)
    chapter_requirements: list[str] = Field(default_factory=list)
    pacing_controls: list[str] = Field(default_factory=list)
    relationship_progression: list[str] = Field(default_factory=list)
    reader_promise: str = ""
    prose_controls: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    originality_guardrails: list[str] = Field(default_factory=list)


class InjectionBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    chapter_hint: int | None = None


class InjectionCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: str = "supporting"
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
    species: str = "werewolf"
    rank: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tropes: list[str] = Field(default_factory=list)


class InjectionWorldRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str = "general"
    description: str
    is_hard_constraint: bool = True


class InjectionWorld(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    summary: str
    geography: str = ""
    factions: list[str] = Field(default_factory=list)
    rules: list[InjectionWorldRule] = Field(default_factory=list)


class InjectionArc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    sequence: int
    summary: str
    start_chapter_number: int | None = None
    end_chapter_number: int | None = None


class InjectionScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str
    goal: str
    conflict: str
    turning_point: str
    dialogue_goal: str
    emotion: str
    information_revealed: str
    ending: str


class InjectionChapterCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_number: int
    title: str
    purpose: str
    conflict: str
    emotional_turn: str
    reveal: str
    hook: str
    location: str = "Primary story setting"
    foreshadowing: str = ""
    setup: str = ""
    payoff: str = ""
    scenes: list[InjectionScene] = Field(default_factory=list)


class InjectionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    premise: str
    theme: str
    tone: str
    narrative_style: str
    pov: str = "third_limited"
    tense: str = "past"
    romance_level: str = "high"
    violence_level: str = "medium"
    heat_level: str = "medium"
    logline: str
    synopsis: str
    tropes: list[str] = Field(default_factory=list)
    plot_structure: str
    plot_summary: str
    beats: list[InjectionBeat] = Field(default_factory=list)
    style_guide: str
    chapter_plan_rules: list[str] = Field(default_factory=list)
    originality_notes: list[str] = Field(default_factory=list)
    world: InjectionWorld | None = None
    characters: list[InjectionCharacter] = Field(default_factory=list)
    arcs: list[InjectionArc] = Field(default_factory=list)
    opening_chapters: list[InjectionChapterCard] = Field(default_factory=list)
    rhythm_controls: list[str] = Field(default_factory=list)
    relationship_progression: list[str] = Field(default_factory=list)
    reader_promise: str = ""
