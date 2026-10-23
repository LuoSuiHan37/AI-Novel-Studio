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
    subtype: str = ""
    narrative_engine: str = ""
    behavior_rotation: list[str] = Field(default_factory=list)
    reveal_policy: list[str] = Field(default_factory=list)
    anti_template_rules: list[str] = Field(default_factory=list)
    phase_rules: dict[str, list[str]] = Field(default_factory=dict)


_GENRE_PRESETS: dict[str, dict[str, Any]] = {
    "werewolf_romance": {
        "genre_label": "狼人罗曼史",
        "subgenres": ["契约婚姻", "身份悬疑", "族群权力"],
        "required_elements": ["狼族规则或血脉代价", "核心男女关系", "契约或替嫁绑定", "可验证的外部威胁", "关系选择带来现实代价"],
        "forbidden_drift": ["连续无冲突甜宠日常", "只靠误会拖延", "普通都市恋爱", "与狼族规则无关的纯悬疑支线"],
        "title_signals": ["狼王", "月圆", "契约", "替嫁", "失控", "血脉", "族规", "新婚夜"],
        "tone": "危险、暧昧、快节奏、情绪有反差，甜与危机交替",
        "relationship_engine": "契约谈判、身份隐瞒、互相试探、被迫结盟、信任代价与重新选择",
        "conflict_engine": "替嫁身份、狼族月圆失控规则、失踪旧案和族群权力互相牵制；每次靠近都必须付出暴露秘密或失去保护的代价",
        "work_tags": {"style": ["暗黑", "悬疑", "快节奏"], "role": ["男主", "女主", "强强"], "plot": ["契约婚姻", "替嫁", "身份反转"], "background": ["兽世", "幻想言情"]},
        "subtype": "forced marriage and hidden-identity pack-power romance",
        "narrative_engine": "以具体事件推动信息差：规则触发危机，人物在限时压力下做选择，选择立即改变关系、身份或安全边界",
        "behavior_rotation": ["女主主动查证并承担暴露代价", "狼王在失控边缘选择自我约束", "族群权威公开施压", "盟友提供互相矛盾的证据", "一次公开选择改变婚约或族内地位"],
        "reveal_policy": ["每章只推进一个主谜团", "重大真相必须先以证据或行动出现，再给解释", "月圆规则带来的后果必须先发生，不能只口头预告"],
        "anti_template_rules": ["不要连续使用警告—地下室—秘密揭示的同一场景形状", "不要用旁白直接宣布心动或害怕，改用选择、身体反应和对话阻力表现", "每章至少有一次局势不可逆变化"],
    },
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
    "palace_house": {
        "genre_label": "古代宅斗",
        "subgenres": ["古代言情", "家宅权力", "旧案翻查"],
        "required_elements": ["家宅或宗族权力", "核心关系", "利益或名分冲突", "具体证据或行动"],
        "forbidden_drift": ["无因由的连续反转", "只靠解释推进", "脱离家宅因果的空泛朝堂线"],
        "title_signals": ["侯府", "中馈", "账", "族老", "婚书", "世子", "旧案"],
        "tone": "克制、锋利、利益与情感交织",
        "relationship_engine": "试探、合作、边界谈判、信任与代价",
        "conflict_engine": "中馈、婆媳、族权和旧案逐层升级",
    },
    "historical_romance": {
        "genre_label": "古代言情",
        "subgenres": ["家宅", "权谋", "情感成长"],
        "required_elements": ["时代与身份约束", "核心关系", "现实利益冲突"],
        "forbidden_drift": ["现代口吻破坏时代感", "无因由的万能反转", "脱离人物能力的解决方案"],
        "title_signals": ["婚书", "侯府", "世子", "王府", "旧案", "圣旨"],
        "tone": "具体、克制、因果清晰",
        "relationship_engine": "试探、协作、误解、选择与承诺",
        "conflict_engine": "身份、家族、制度和情感持续碰撞",
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
        defaults = compile_creative_contract(
            genre=getattr(project, "genre", ""),
            audience="女频" if "romance" in getattr(project, "genre", "") else "",
            language=getattr(project, "language", ""),
        )
        # Older projects may contain partially written contracts. Empty lists and
        # strings must not erase the current genre preset after a code update.
        merged = dict(defaults)
        for key, value in existing.items():
            if value not in (None, "", [], {}):
                merged[key] = value
        if not merged.get("work_tags"):
            merged["work_tags"] = defaults.get("work_tags", {})
        legacy_werewolf_tags = {
            "plot": ["现代言情"],
            "role": ["女主"],
            "style": ["甜宠"],
            "background": ["都市"],
        }
        if getattr(project, "genre", "") == "werewolf_romance" and merged.get("work_tags") == legacy_werewolf_tags:
            merged["work_tags"] = defaults.get("work_tags", {})
        if getattr(project, "genre", "") == "werewolf_romance" and merged.get("genre_label") == "werewolf romance":
            merged["genre_label"] = defaults.get("genre_label", merged["genre_label"])
        return merged
    return compile_creative_contract(
        genre=getattr(project, "genre", ""),
        audience="女频" if "romance" in getattr(project, "genre", "") else "",
        language=getattr(project, "language", ""),
    )
