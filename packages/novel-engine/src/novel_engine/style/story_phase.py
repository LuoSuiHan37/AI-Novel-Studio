from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoryPhase:
    key: str
    label: str
    basis: str


def classify_story_phase(*, chapter_number: int, target_chapters: int | None = None) -> StoryPhase:
    """Deterministic phase classification used as a planning constraint.

    This is intentionally a coarse planning signal, not a claim about literary
    structure. A saved project may override it later with an explicit arc phase.
    """
    number = max(1, chapter_number)
    if number <= 3:
        return StoryPhase("opening", "开局建立", "前3章固定为开局建立")
    if not target_chapters:
        if number <= 12:
            return StoryPhase("binding", "主线绑定", "未设置总章数时的前12章")
        if number <= 30:
            return StoryPhase("investigation", "初步调查", "未设置总章数时的13—30章")
        if number <= 60:
            return StoryPhase("escalation", "矛盾升级", "未设置总章数时的31—60章")
        return StoryPhase("crisis", "危机收束", "未设置总章数时的61章以后")
    ratio = number / max(1, target_chapters)
    if ratio <= 0.12:
        return StoryPhase("binding", "主线绑定", "章节进度不超过12%")
    if ratio <= 0.42:
        return StoryPhase("investigation", "初步调查", "章节进度不超过42%")
    if ratio <= 0.68:
        return StoryPhase("escalation", "矛盾升级", "章节进度不超过68%")
    if ratio <= 0.88:
        return StoryPhase("reversal", "中段反转", "章节进度不超过88%")
    return StoryPhase("crisis", "高潮收束", "章节进度超过88%")
