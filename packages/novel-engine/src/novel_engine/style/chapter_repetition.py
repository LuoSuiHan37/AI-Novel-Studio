from __future__ import annotations

import re
import hashlib
from difflib import SequenceMatcher
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field


class ChapterRepetitionMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_number: int
    similarity: float
    repeated_paragraph_ratio: float
    exact: bool = False
    reason: str


class ChapterRepetitionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "passed"
    blocked: bool = False
    exact_hash: str
    max_similarity: float = 0.0
    matches: list[ChapterRepetitionMatch] = Field(default_factory=list)


_SPACE = re.compile(r"\s+")
_PARAGRAPH = re.compile(r"\n+|(?<=[。！？!?\.])\s+")


def normalize_prose(text: str) -> str:
    """Normalize prose for exact duplicate checks without removing punctuation."""

    return _SPACE.sub(" ", text).strip().casefold()


def _paragraphs(text: str) -> set[str]:
    return {
        item
        for item in (normalize_prose(part) for part in _PARAGRAPH.split(text))
        if len(item) >= 24
    }


def _content_units(text: str) -> int:
    return len(re.findall(r"\w+|[^\s]", text, flags=re.UNICODE))


def _semantic_tokens(text: str) -> list[str]:
    """Return stable lexical units for paraphrase-resistant duplicate checks.

    This is intentionally provider-free.  It cannot prove semantic equivalence,
    but it catches reordered prose and light rewriting that character-level
    similarity misses.
    """
    lowered = normalize_prose(text)
    words = re.findall(r"[a-z0-9][a-z0-9'_-]{1,}|[\u3400-\u9fff]", lowered)
    return [" ".join(words[index:index + 2]) for index in range(max(0, len(words) - 1))]


def scan_chapter_repetition(
    *,
    chapter_number: int,
    content: str,
    chapters: Iterable[object],
) -> ChapterRepetitionReport:
    """Compare one chapter with every other non-empty chapter in the project.

    Exact content and large repeated blocks are hard blockers.  Small shared
    phrases and normal recap paragraphs are intentionally not blockers.
    """

    normalized = normalize_prose(content)
    exact_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    current_paragraphs = _paragraphs(content)
    matches: list[ChapterRepetitionMatch] = []
    for chapter in chapters:
        other_number = int(getattr(chapter, "chapter_number"))
        other_content = str(getattr(chapter, "content", "") or "")
        if other_number == chapter_number or not other_content.strip():
            continue
        other_normalized = normalize_prose(other_content)
        if not other_normalized:
            continue
        exact = normalized == other_normalized
        similarity = SequenceMatcher(None, normalized, other_normalized, autojunk=False).ratio()
        current_tokens = _semantic_tokens(content)
        other_tokens = _semantic_tokens(other_content)
        token_similarity = SequenceMatcher(None, current_tokens, other_tokens, autojunk=False).ratio()
        token_union = set(current_tokens) | set(other_tokens)
        token_jaccard = (
            len(set(current_tokens) & set(other_tokens)) / len(token_union)
            if token_union
            else 0.0
        )
        other_paragraphs = _paragraphs(other_content)
        repeated_ratio = (
            len(current_paragraphs & other_paragraphs) / len(current_paragraphs)
            if current_paragraphs
            else 0.0
        )
        units = min(_content_units(content), _content_units(other_content))
        blocked = exact or (
            units >= 120
            and repeated_ratio >= 0.50
            and len(current_paragraphs & other_paragraphs) >= 2
        ) or (units >= 300 and similarity >= 0.86) or (
            units >= 180 and token_similarity >= 0.48 and token_jaccard >= 0.30
        )
        if blocked:
            if exact:
                reason = "正文与另一章完全重复"
            elif repeated_ratio >= 0.50:
                reason = "至少一半正文段落与另一章重复"
            elif token_similarity >= 0.48 and token_jaccard >= 0.30:
                reason = "正文经过改写后仍与另一章存在高度相同的叙事表达"
            else:
                reason = "正文整体相似度过高"
            matches.append(
                ChapterRepetitionMatch(
                    chapter_number=other_number,
                    similarity=round(similarity, 4),
                    repeated_paragraph_ratio=round(repeated_ratio, 4),
                    exact=exact,
                    reason=reason,
                )
            )
    matches.sort(key=lambda item: (item.exact, item.repeated_paragraph_ratio, item.similarity), reverse=True)
    return ChapterRepetitionReport(
        status="blocked" if matches else "passed",
        blocked=bool(matches),
        exact_hash=exact_hash,
        max_similarity=max((item.similarity for item in matches), default=0.0),
        matches=matches[:10],
    )


def scan_book_repetition(chapters: Iterable[object]) -> list[dict]:
    """Return each blocking pair once for a full-book pre-publish scan."""

    ordered = sorted(
        [item for item in chapters if str(getattr(item, "content", "") or "").strip()],
        key=lambda item: int(getattr(item, "chapter_number")),
    )
    findings: list[dict] = []
    for index, chapter in enumerate(ordered):
        report = scan_chapter_repetition(
            chapter_number=int(getattr(chapter, "chapter_number")),
            content=str(getattr(chapter, "content", "") or ""),
            chapters=[*ordered[:index], *ordered[index + 1 :]],
        )
        for match in report.matches:
            if int(getattr(chapter, "chapter_number")) < match.chapter_number:
                findings.append(
                    {
                        "chapter_number": int(getattr(chapter, "chapter_number")),
                        "matched_chapter_number": match.chapter_number,
                        **match.model_dump(exclude={"chapter_number"}),
                    }
                )
    return findings
