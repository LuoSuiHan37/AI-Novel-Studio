from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreativeContract(BaseModel):
    """The reader-facing genre promise shared by every generation stage."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0"
    primary_genre: str = ""
    genre_label: str = ""
    subgenres: list[str] = Field(default_factory=list)
    audience: str = ""
    core_promise: str = ""
    required_elements: list[str] = Field(default_factory=list)
    forbidden_drift: list[str] = Field(default_factory=list)
    title_signals: list[str] = Field(default_factory=list)
    tone: str = ""
    relationship_engine: str = ""
    conflict_engine: str = ""
    work_tags: dict[str, list[str]] = Field(default_factory=dict)


_GENRE_PRESETS: dict[str, dict[str, Any]] = {
    "billionaire_romance": {
        "genre_label": "豪门总裁",
        "subgenres": ["职场权谋", "身份反转", "契约关系"],
        "required_elements": ["豪门或权力阶层", "总裁或继承人", "核心男女关系", "身份或利益冲突"],
        "forbidden_drift": ["普通职场日常", "办公室悬疑", "单纯推理", "低冲突加班故事"],
        "title_signals": ["豪门", "总裁", "继承人", "契约", "婚约", "夫人", "身份", "股权", "董事会"],
        "tone": "强冲突、身份差、暧昧拉扯、权力斗争",
        "relationship_engine": "试探、利用、结盟、暧昧、决裂与选择",
        "conflict_engine": "股权、继承权、董事会和身份秘密共同升级",
    },
    "workplace_romance": {
        "genre_label": "职场婚恋",
        "subgenres": ["职场成长", "都市情感"],
        "required_elements": ["职场处境", "核心情感关系", "职业选择或成长"],
        "forbidden_drift": ["纯案件推理", "脱离职业线的空泛恋爱"],
        "title_signals": ["职场", "恋爱", "婚姻", "上司", "同事"],
        "tone": "现实、克制、暧昧、成长",
        "relationship_engine": "合作、误会、靠近与承诺",
        "conflict_engine": "职业压力与情感选择相互牵制",
    },
    "contemporary_romance": {
        "genre_label": "现代言情",
        "subgenres": ["都市情感"],
        "required_elements": ["核心男女关系", "现实处境", "情感推进"],
        "forbidden_drift": ["连续无冲突日常", "纯悬疑推理"],
        "title_signals": ["爱", "婚约", "前任", "隐婚", "心动", "重逢"],
        "tone": "现代、情感化、强关系推进",
        "relationship_engine": "相遇、试探、误会、确认与选择",
        "conflict_engine": "现实阻力与情感需求持续碰撞",
    },
}


def compile_creative_contract(
    *,
    genre: str,
    audience: str = "",
    core_promise: str = "",
    premise: str = "",
    theme: str = "",
    language: str = "",
    work_tags: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    preset = _GENRE_PRESETS.get(genre, {})
    label = preset.get("genre_label") or genre.replace("_", " ")
    promise = core_promise or premise or theme
    raw = {
        "primary_genre": genre,
        "genre_label": label,
        "audience": audience or ("女频" if "romance" in genre else ""),
        "core_promise": promise,
        "language": language,
        "work_tags": work_tags or {},
        **preset,
    }
    return CreativeContract.model_validate(raw).model_dump(mode="json")


def contract_for_project(project: Any) -> dict[str, Any]:
    metadata = getattr(project, "extra_metadata", None) or {}
    existing = metadata.get("creative_contract")
    if isinstance(existing, dict) and existing.get("primary_genre"):
        return existing
    return compile_creative_contract(
        genre=getattr(project, "genre", ""),
        audience="女频" if "romance" in getattr(project, "genre", "") else "",
        language=getattr(project, "language", ""),
    )
