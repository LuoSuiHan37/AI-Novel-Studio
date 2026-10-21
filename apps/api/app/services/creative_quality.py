from __future__ import annotations

import re
from collections.abc import Iterable


_GENERIC_TITLE_PARTS = (
    "我的总裁",
    "霸道总裁",
    "重生后我",
    "系统让我",
    "chapter",
    "untitled",
)
_HOOK_MARKERS = tuple("却但竟然原来直到为何谁才秘密真相" )
_SENTENCE_LIKE_TITLE_PARTS = (
    "到最后", "最后一行", "最后一页", "然后", "于是", "因为", "并且",
    "她去", "他去", "我去", "她在", "他在", "我在", "复核", "核对",
)
_GENRE_TITLE_SIGNALS: dict[str, tuple[str, ...]] = {
    "billionaire_romance": ("豪门", "总裁", "太子爷", "继承人", "契约", "婚约", "夫人", "身份", "股权"),
    "workplace_romance": ("闪婚", "离婚", "二婚", "远嫁", "合同", "上司", "追妻", "婚姻", "太子爷"),
    "republican_romance": ("军阀", "少帅", "民国", "夫人", "督军", "乱世", "婚约"),
    "showbiz_romance": ("影帝", "顶流", "爱豆", "女星", "直播", "隐婚", "官宣", "塌房", "娱乐圈"),
    "youth_sweet": ("同桌", "学霸", "校草", "少年", "校园", "重生", "团宠", "初恋"),
    "mystery_what_if": ("求生", "规则怪谈", "NPC", "无限流", "诡异", "副本", "系统", "末日"),
    "ancient_romance_what_if": ("王爷", "太子", "主母", "皇后", "将军", "反派", "重生", "穿书", "退婚", "逃荒"),
}
_ABSTRACT_CHAPTER_TITLES = {
    "重签", "旧雨", "见证", "退让", "反证", "私谈", "裂痕", "取件", "对质", "倒签",
    "相遇", "重逢", "误会", "真相", "选择", "决定", "转折", "危机", "秘密", "发现",
    "谈判", "回归", "离开", "背叛", "承诺", "觉醒", "反击", "终局", "新生", "告白",
}


def make_reader_facing_chapter_title(
    title: str,
    *,
    conflict: str = "",
    cliffhanger: str = "",
    chapter_goal: str = "",
) -> str:
    """Keep AI-generated chapter titles concrete enough for a serial reader.

    Short poetic titles are allowed when a human supplies them, but planner
    output must not silently collapse into an abstract outline label. When the
    model does that, append the strongest concrete pressure already present in
    the plan instead of inventing a new plot event.
    """
    clean = _clean(title)
    if _normalise(clean) not in {_normalise(item) for item in _ABSTRACT_CHAPTER_TITLES}:
        return clean
    detail = next((item.strip().rstrip("。.!！?？") for item in (cliffhanger, conflict, chapter_goal) if item and item.strip()), "")
    if not detail:
        return clean
    return f"{clean}：{detail[:24]}"


def rank_creative_candidates(
    candidates: Iterable[str],
    *,
    existing: Iterable[str] = (),
    genre: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Rank reader-facing candidates with transparent, conservative heuristics.

    The LLM remains responsible for creative quality. This only removes empty,
    duplicate, overlong, obviously generic, or already-used candidates and gives
    the UI a reasoned score for human selection.
    """
    existing_keys = {_normalise(item) for item in existing if item}
    seen: set[str] = set()
    ranked: list[dict] = []
    for raw in candidates:
        value = _clean(raw)
        key = _normalise(value)
        if not value or key in seen or key in existing_keys or re.fullmatch(r"chapter\s*\d+", value, re.IGNORECASE):
            continue
        seen.add(key)
        score = 55
        reasons: list[str] = []
        length = len(value)
        if 5 <= length <= 24:
            score += 15
            reasons.append("长度适合移动端展示")
        elif length > 32:
            score -= 15
            reasons.append("标题偏长")
        if any(marker in value.casefold() for marker in _GENERIC_TITLE_PARTS):
            score -= 12
            reasons.append("存在常见模板表达")
        if any(marker in value for marker in _HOOK_MARKERS):
            score += 12
            reasons.append("包含冲突或悬念词")
        if any(marker in value for marker in _SENTENCE_LIKE_TITLE_PARTS):
            score -= 30
            reasons.append("像情节句或工作记录，不像书名")
        if any(char in value for char in "：:，,？！?!"):
            score += 4
        if genre in _GENRE_TITLE_SIGNALS:
            if any(marker in value for marker in _GENRE_TITLE_SIGNALS[genre]):
                score += 18
                reasons.append("包含题材识别信号")
            if genre in {"billionaire_romance", "workplace_romance"} and any(marker in value for marker in ("工位", "加班", "办公室", "会议室", "电话")):
                score -= 18
                reasons.append("容易被误读为普通职场故事")
            if genre == "workplace_romance" and any(marker in value for marker in ("合同", "债", "上司", "背叛", "证据", "反转", "真相", "失控", "追妻", "离婚", "婚姻")):
                score += 18
                reasons.append("明确呈现职场婚恋冲突")
            if genre == "mystery_what_if" and any(marker in value for marker in ("求生", "规则", "怪谈", "NPC", "副本", "诡异", "无限流")):
                score += 12
                reasons.append("明确呈现脑洞悬疑设定")
            if genre == "showbiz_romance" and any(marker in value for marker in ("翻车", "塌房", "官宣", "隐婚", "重生", "追妻", "失控")):
                score += 12
                reasons.append("明确呈现娱乐圈反差冲突")
        score = max(0, min(100, score))
        ranked.append({"text": value, "score": score, "reasons": reasons})
    ranked.sort(key=lambda item: (-item["score"], item["text"]))
    return ranked[:limit]


def _clean(value: str) -> str:
    return re.sub(r"^第?\s*\d+\s*[章节回：:、.\- ]*", "", value.strip().strip('"\'“”‘’'))


def _normalise(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()
