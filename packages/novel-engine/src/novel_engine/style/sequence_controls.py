from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field


_SENTENCE = re.compile(r"[^。！？!?；;]+[。！？!?；;]?")
_CLAUSE = re.compile(r"[。！？!?；;，,、\n]+")
_TOKEN = re.compile(r"[a-z0-9][a-z0-9'_-]{1,}|[\u3400-\u9fff]")
_QUOTES = re.compile(r"[\"“”‘’「」『』]")


class ChapterExpressionFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_number: int
    opening_type: str
    ending_type: str
    dominant_images: list[str] = Field(default_factory=list)
    repeated_markers: list[str] = Field(default_factory=list)
    rhythm: str = "mixed"
    dialogue_ratio: float = 0.0
    short_sentence_ratio: float = 0.0
    behavior_modes: list[str] = Field(default_factory=list)
    approved: bool = False


class ExpressionHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapters: list[ChapterExpressionFingerprint] = Field(default_factory=list)


class SequenceWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    item: str
    chapters: list[int] = Field(default_factory=list)
    note: str
    recommendation: str


class RevealRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_number: int
    items: list[str] = Field(default_factory=list)


class RevealLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[RevealRecord] = Field(default_factory=list)


def _sentences(prose: str) -> list[str]:
    return [item.strip() for item in _SENTENCE.findall(prose) if item.strip()]


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


def _plan_text(plan: object, scenes: list[object]) -> str:
    parts = [
        getattr(plan, "location", ""),
        getattr(plan, "conflict", ""),
        getattr(plan, "cliffhanger", ""),
    ]
    for scene in scenes:
        parts.extend(
            getattr(scene, name, "")
            for name in ("location", "conflict", "turning_point", "information_revealed", "ending")
        )
    return " ".join(str(item) for item in parts if item)


def _ending_type(plan: object, prose: str) -> str:
    text = f"{getattr(plan, 'cliffhanger', '')} {prose[-240:]}"
    if any(word in text for word in ("选择", "决定", "答应", "拒绝", "代价")):
        return "decision_or_cost"
    if any(word in text for word in ("发现", "看见", "认出", "秘密", "真相")):
        return "discovery"
    if any(word in text for word in ("追", "袭", "攻击", "塌", "危险", "心跳", "裂")):
        return "danger_escalation"
    return "consequence_or_transition"


def fingerprint_chapter(
    *, chapter_number: int, prose: str, plan: object, scenes: list[object], watchlist: list[str]
) -> ChapterExpressionFingerprint:
    sentences = _sentences(prose)
    sentence_lengths = [len(_tokens(item)) for item in sentences] or [0]
    short_ratio = sum(length <= 12 for length in sentence_lengths) / len(sentence_lengths)
    dialogue_ratio = len(_QUOTES.findall(prose)) / max(1, len(prose))
    opening = prose.lstrip()[:180]
    if opening.startswith(("\"", "“", "‘", "「", "『")):
        opening_type = "dialogue"
    elif any(word in opening for word in ("跑", "冲", "跳", "抓", "拔", "推", "砍", "起身")):
        opening_type = "direct_action"
    elif "他" in opening or "她" in opening or "凯尔" in opening:
        opening_type = "character_observation"
    else:
        opening_type = "environment_or_setup"

    markers = ("像", "盯着", "沉默", "低鸣", "一明一灭", "声音", "震动", "蓝光", "心跳", "雾")
    marker_counts = Counter(marker for marker in markers if prose.count(marker) >= 3)
    images = Counter()
    watched = set(watchlist)
    for phrase in [*watchlist, *re.findall(r"[\u3400-\u9fff]{2,4}", _plan_text(plan, scenes))]:
        minimum = 1 if phrase in watched else 2
        if phrase and prose.count(phrase) >= minimum:
            images[phrase] += prose.count(phrase)
    rhythm = "short_dense" if short_ratio >= 0.65 else "long_reflective" if short_ratio <= 0.35 else "mixed"
    behavior_markers = {
        "protective_rescue": ("挡在", "护住", "替她", "替他", "救下", "保护"),
        "withholding": ("现在不行", "不能告诉", "没回答", "没有回答", "不答", "沉默"),
        "interrogation": ("你告诉我", "为什么", "到底是谁", "怎么回事", "问道"),
        "deduction": ("账", "核对", "算出", "数字", "票号", "旧册"),
        "confrontation": ("我不同意", "不可能", "你说了算", "反问", "逼问"),
    }
    behavior_modes = [
        name for name, markers_for_mode in behavior_markers.items()
        if sum(prose.count(marker) for marker in markers_for_mode) >= 2
    ]
    return ChapterExpressionFingerprint(
        chapter_number=chapter_number,
        opening_type=opening_type,
        ending_type=_ending_type(plan, prose),
        dominant_images=[item for item, _ in images.most_common(6)],
        repeated_markers=[item for item, _ in marker_counts.most_common(6)],
        rhythm=rhythm,
        dialogue_ratio=round(dialogue_ratio, 4),
        short_sentence_ratio=round(short_ratio, 4),
        behavior_modes=behavior_modes,
    )


def assess_expression_sequence(
    current: ChapterExpressionFingerprint, history: ExpressionHistory, recent_window: int = 3
) -> list[SequenceWarning]:
    prior = [item for item in history.chapters if current.chapter_number - recent_window <= item.chapter_number < current.chapter_number]
    warnings: list[SequenceWarning] = []
    for field, label, recommendation in (
        ("opening_type", "opening", "改变开场方式，例如从人物行动、物证或对话冲突开始。"),
        ("ending_type", "ending", "不要再次用同一种结尾功能，改用决定、代价、误判或关系变化。"),
        ("rhythm", "rhythm", "改变段落节奏，增加长短句、行动与对白的交替。"),
    ):
        same = [item.chapter_number for item in prior if getattr(item, field) == getattr(current, field)]
        if len(same) >= 2:
            warnings.append(SequenceWarning(
                category=f"repeated_{label}", item=getattr(current, field), chapters=[*same, current.chapter_number],
                note=f"最近章节连续使用相同的{label}模式。", recommendation=recommendation,
            ))
    prior_images = {image for item in prior for image in item.dominant_images}
    repeated_images = [image for image in current.dominant_images if image in prior_images]
    if len(repeated_images) >= 2:
        warnings.append(SequenceWarning(
            category="repeated_imagery", item="、".join(repeated_images),
            chapters=[item.chapter_number for item in prior] + [current.chapter_number],
            note="连续章节重复使用同一组主要意象。", recommendation="保留必要意象，但更换本章的主要感官和叙事功能。",
        ))
    prior_behaviors = {mode for item in prior for mode in item.behavior_modes}
    repeated_behaviors = [mode for mode in current.behavior_modes if mode in prior_behaviors]
    if repeated_behaviors:
        warnings.append(SequenceWarning(
            category="repeated_character_behavior", item="、".join(repeated_behaviors),
            chapters=[item.chapter_number for item in prior] + [current.chapter_number],
            note="主角或核心角色连续使用相同的行为功能。",
            recommendation="改变角色的解决方式，让本章出现误判、独立行动、让步、失败或新的关系代价。",
        ))
    return warnings


def reveal_items(plan: object, scenes: list[object]) -> list[str]:
    values = [getattr(plan, name, "") for name in ("new_information", "reveal")]
    values.extend(getattr(scene, "information_revealed", "") for scene in scenes)
    items: list[str] = []
    for value in values:
        for item in _CLAUSE.split(str(value or "")):
            item = item.strip(" ：:.-")
            if len(_tokens(item)) >= 3 and item not in items:
                items.append(item)
    return items


def _overlap(left: str, right: str) -> float:
    a, b = set(_tokens(left)), set(_tokens(right))
    return len(a & b) / max(1, len(a | b))


def assess_reveal_plan(*, plan: object, scenes: list[object], ledger: RevealLedger, chapter_number: int) -> list[SequenceWarning]:
    items = reveal_items(plan, scenes)
    warnings: list[SequenceWarning] = []
    if len(items) > 4:
        warnings.append(SequenceWarning(
            category="reveal_budget", item=str(len(items)), chapters=[chapter_number],
            note="本章计划一次安排了过多信息揭示。", recommendation="最多保留两个新事实、一个新疑问，其余改为线索或延后揭示。",
        ))
    recent = [record for record in ledger.records if chapter_number - 4 <= record.chapter_number < chapter_number]
    for item in items:
        matches = [record.chapter_number for record in recent if any(_overlap(item, old) >= 0.6 for old in record.items)]
        if matches:
            warnings.append(SequenceWarning(
                category="repeated_reveal", item=item, chapters=[*matches, chapter_number],
                note="本章计划重复解释近期已经出现的信息。", recommendation="改为新增物证、人物误判或后果，不要再次直接解释。",
            ))
    return warnings


def build_sequence_guidance(*, history: ExpressionHistory, ledger: RevealLedger, plan: object, scenes: list[object]) -> list[str]:
    current = fingerprint_chapter(chapter_number=0, prose="", plan=plan, scenes=scenes, watchlist=[])
    recent = history.chapters[-3:]
    notes: list[str] = []
    recent_images = {image for item in recent for image in item.dominant_images}
    if recent_images:
        notes.append("连续表达约束：最近章节已高频使用 " + "、".join(sorted(recent_images)[:6]) + "，本章不要让同一组意象继续承担主要悬念。")
    if recent and all(item.ending_type == "danger_escalation" for item in recent):
        notes.append("连续表达约束：最近章节连续使用危险升级式结尾，本章优先使用人物选择、代价、误判或关系变化结尾。")
    recent_behaviors = {mode for item in recent for mode in item.behavior_modes}
    if recent_behaviors:
        notes.append("角色行为约束：最近章节已使用 " + "、".join(sorted(recent_behaviors)) + "，本章不要让核心角色重复同一种解决方式。")
    reveal_warnings = assess_reveal_plan(plan=plan, scenes=scenes, ledger=ledger, chapter_number=999999)
    if reveal_warnings:
        notes.extend("信息揭示约束：" + warning.recommendation for warning in reveal_warnings)
    else:
        notes.append("信息揭示约束：本章最多明确揭示两个新事实，保留至少一个关键疑问，不要让人物一次性解释完整背景。")
    return notes


def record_expression(
    history: ExpressionHistory,
    fingerprint: ChapterExpressionFingerprint,
    *,
    approved: bool | None = None,
) -> None:
    if approved is not None:
        fingerprint = fingerprint.model_copy(update={"approved": approved})
    history.chapters = [item for item in history.chapters if item.chapter_number != fingerprint.chapter_number]
    history.chapters.append(fingerprint)
    history.chapters.sort(key=lambda item: item.chapter_number)


def record_reveals(ledger: RevealLedger, *, chapter_number: int, items: list[str]) -> None:
    ledger.records = [item for item in ledger.records if item.chapter_number != chapter_number]
    ledger.records.append(RevealRecord(chapter_number=chapter_number, items=items))
    ledger.records.sort(key=lambda item: item.chapter_number)
