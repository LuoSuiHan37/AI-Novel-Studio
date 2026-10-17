from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ContinuitySignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_contains: str
    error_if_prose_contains: list[str] = Field(default_factory=list)
    unless_prose_contains: list[str] = Field(default_factory=list)


class PlatformPreset(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    language: str = "English"
    audience: str = "female"
    pacing: str = "fast"
    paragraph_style: str = "short"
    chapter_word_min: int = 1500
    chapter_word_max: int = 2500
    required_beats: list[str] = Field(default_factory=list)
    ending: str = "hook_or_cliffhanger"
    primary_genres: list[str] = Field(default_factory=list)
    writing_rules: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    monitored_phrases: list[str] = Field(default_factory=list)
    continuity_signals: list[ContinuitySignal] = Field(default_factory=list)
    literary_requirements: list[str] = Field(default_factory=list)
    environment_requirements: list[str] = Field(default_factory=list)


class NovelPreset(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    genres: list[str] = Field(default_factory=list)
    default_platform: str | None = None
    tropes: list[str] = Field(default_factory=list)
    writing_rules: list[str] = Field(default_factory=list)
    continuity_signals: list[ContinuitySignal] = Field(default_factory=list)
    subtype: str = ""
    narrative_engine: str = ""
    behavior_rotation: list[str] = Field(default_factory=list)
    reveal_policy: list[str] = Field(default_factory=list)
    anti_template_rules: list[str] = Field(default_factory=list)
    phase_rules: dict[str, list[str]] = Field(default_factory=dict)


class StyleBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: PlatformPreset
    novel: NovelPreset

    @property
    def style_guide(self) -> str:
        lines = [
            f"Platform preset: {self.platform.name} ({self.platform.id})",
            f"Novel preset: {self.novel.name} ({self.novel.id})",
            f"Language: {self.platform.language}",
            f"Audience: {self.platform.audience}",
            f"Pacing: {self.platform.pacing}; paragraphs: {self.platform.paragraph_style}",
            f"Chapter target words: {self.platform.chapter_word_min}-{self.platform.chapter_word_max}",
            f"Required beats: {', '.join(self.platform.required_beats)}",
            f"Ending: {self.platform.ending}",
        ]
        lines.append("Rules:")
        lines.extend(f"- {item}" for item in [*self.platform.writing_rules, *self.novel.writing_rules])
        if self.novel.subtype:
            lines.append(f"Sub-genre: {self.novel.subtype}")
        if self.novel.narrative_engine:
            lines.append(f"Narrative engine: {self.novel.narrative_engine}")
        if self.novel.behavior_rotation:
            lines.append("Behavior rotation:")
            lines.extend(f"- {item}" for item in self.novel.behavior_rotation)
        if self.novel.reveal_policy:
            lines.append("Reveal policy:")
            lines.extend(f"- {item}" for item in self.novel.reveal_policy)
        if self.novel.anti_template_rules:
            lines.append("Anti-template rules:")
            lines.extend(f"- {item}" for item in self.novel.anti_template_rules)
        if self.novel.phase_rules:
            lines.append("Phase rules (select only the current phase):")
            for phase, rules in self.novel.phase_rules.items():
                lines.append(f"- {phase}: " + "；".join(rules))
        if self.platform.avoid:
            lines.append("Avoid:")
            lines.extend(f"- {item}" for item in self.platform.avoid)
        if self.platform.literary_requirements:
            lines.append("Literary requirements:")
            lines.extend(f"- {item}" for item in self.platform.literary_requirements)
        if self.platform.environment_requirements:
            lines.append("Environment requirements:")
            lines.extend(f"- {item}" for item in self.platform.environment_requirements)
        return "\n".join(lines)

    def signals(self) -> list[ContinuitySignal]:
        return [*self.platform.continuity_signals, *self.novel.continuity_signals]
