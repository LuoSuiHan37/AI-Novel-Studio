from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NovelConstitution(BaseModel):
    """The book-level contract that must remain isolated per novel."""

    model_config = ConfigDict(extra="ignore")

    core_question: str = ""
    reader_promise: str = ""
    ending_direction: str = ""
    themes: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    forbidden_treatments: list[str] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)


class EnvironmentBible(BaseModel):
    """A scene-producing environment, not a decorative location description."""

    model_config = ConfigDict(extra="ignore")

    geography: str = ""
    time_and_climate: str = ""
    sensory_palette: list[str] = Field(default_factory=list)
    social_pressures: list[str] = Field(default_factory=list)
    daily_life_details: list[str] = Field(default_factory=list)
    recurring_locations: list[str] = Field(default_factory=list)
    environmental_constraints: list[str] = Field(default_factory=list)
    recurring_motifs: list[str] = Field(default_factory=list)


class CreativeProfile(BaseModel):
    """Structured book-level creative policy stored under project metadata."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "2.0"
    novel_constitution: NovelConstitution = Field(default_factory=NovelConstitution)
    environment_bible: EnvironmentBible = Field(default_factory=EnvironmentBible)
    character_dynamics: list[str] = Field(default_factory=list)
    relationship_rules: list[str] = Field(default_factory=list)
    literary_review_rubric: list[str] = Field(
        default_factory=lambda: [
            "人物欲望必须具体，且与人物恐惧或误解发生冲突。",
            "每场戏都要改变信息、关系、处境或选择成本中的至少一项。",
            "情绪要通过动作、细节、节奏和潜台词呈现，不能只用情绪标签解释。",
            "环境必须对人物施加压力，不能只是可替换的背景板。",
            "结尾悬念必须由本章因果产生，不能靠突然宣布更大的秘密。",
            "单章只突出一个主冲突和一个主悬念，其他秘密分层释放。",
            "主角必须在本章主动做出一次有代价的选择，而不是只被剧情推动。",
            "结尾优先落在正在发生的行动、决定或迫近危机上，而不是只揭露背景信息。",
        ]
    )
    reader_promise: str = ""
    rhythm_controls: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    chapter_requirements: list[str] = Field(default_factory=list)
    anti_ai_rules: list[str] = Field(default_factory=list)
    style_guide: str = ""


def compile_creative_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize research/UI input while preserving legacy profile fields."""

    raw = dict(profile) if isinstance(profile, dict) else {}
    raw["reader_promise"] = raw.get("reader_promise") or raw.get("positioning", "")
    raw["rhythm_controls"] = raw.get("rhythm_controls") or raw.get("pacing_controls", []) or [
        "前120个汉字内建立人物、处境和一个异常点。",
        "前500个汉字内出现明确的外部冲突或不可回避的压力。",
        "每500至700个汉字至少发生一次信息、关系、处境或选择成本的变化。",
        "一章只保留一个主悬念，次要秘密不得同时抢走注意力。",
        "结尾必须推动一个立即发生的行动、决定或危机。",
    ]
    raw["hard_constraints"] = raw.get("hard_constraints") or [
        *raw.get("opening_requirements", []),
        *raw.get("chapter_requirements", []),
    ]
    raw["anti_ai_rules"] = raw.get("anti_ai_rules") or [
        *raw.get("avoid", []),
        *raw.get("originality_guardrails", []),
        "减少连续比喻、抽象情绪标签和整齐重复的句式。",
        "避免把设定、制度或人物背景集中讲完，优先通过行动和对话释放。",
        "避免连续使用相同的模板化句式起句。",
    ]
    raw["chapter_requirements"] = raw.get("chapter_requirements") or [
        "本章必须有一个清晰的读者承诺，并在正文中兑现一次小回报。",
        "主角必须主动做出一次有风险的选择，并承担可见代价。",
        "本章只围绕一个主冲突推进，至少完成两次局面变化。",
        "结尾使用行动型钩子：下一章会立即发生什么，而不只是新增一个名词或秘密。",
    ]
    compiled = CreativeProfile.model_validate(raw)
    return {
        **raw,
        **compiled.model_dump(mode="json"),
        "schema_version": compiled.schema_version,
    }
