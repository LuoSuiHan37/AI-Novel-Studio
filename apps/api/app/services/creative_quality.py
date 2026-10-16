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
        if any(char in value for char in "：:，,？！?!"):
            score += 4
        if genre == "billionaire_romance":
            if any(marker in value for marker in ("豪门", "总裁", "继承人", "契约", "婚约", "夫人", "身份", "股权", "董事会")):
                score += 18
                reasons.append("符合豪门总裁类型信号")
            else:
                score -= 22
                reasons.append("缺少豪门总裁类型信号")
            if any(marker in value for marker in ("工位", "加班", "办公室", "会议室", "电话")):
                score -= 18
                reasons.append("容易被误读为普通职场故事")
        score = max(0, min(100, score))
        ranked.append({"text": value, "score": score, "reasons": reasons})
    ranked.sort(key=lambda item: (-item["score"], item["text"]))
    return ranked[:limit]


def _clean(value: str) -> str:
    return re.sub(r"^第?\s*\d+\s*[章节回：:、.\- ]*", "", value.strip().strip('"\'“”‘’'))


def _normalise(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()
