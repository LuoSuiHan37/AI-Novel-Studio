from __future__ import annotations

import re
from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field

from novel_engine.style.narrative_fingerprint import NarrativeHistory

_TOKEN = re.compile(r"[a-z']+|[\u3400-\u9fff]")
_QUOTED = re.compile(r'"([^"]{8,80})"')


def _norm(text: str) -> str:
    """Normalize both Latin words and CJK characters for stable matching."""

    return " ".join(_TOKEN.findall(text.casefold()))


def _ngrams(text: str, size: int = 4) -> list[str]:
    tokens = _TOKEN.findall(text.casefold())
    if len(tokens) < size:
        return []
    return [" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)]


class StyleHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phrases: dict[str, list[int]] = Field(default_factory=lambda: defaultdict(list))
    scene_patterns: dict[str, list[int]] = Field(default_factory=lambda: defaultdict(list))
    conflicts: dict[str, list[int]] = Field(default_factory=lambda: defaultdict(list))
    dialogue_patterns: dict[str, list[int]] = Field(default_factory=lambda: defaultdict(list))
    narrative: NarrativeHistory = Field(default_factory=NarrativeHistory)

    def model_post_init(self, _context) -> None:
        self.phrases = defaultdict(list, self.phrases)
        self.scene_patterns = defaultdict(list, self.scene_patterns)
        self.conflicts = defaultdict(list, self.conflicts)
        self.dialogue_patterns = defaultdict(list, self.dialogue_patterns)


class RepetitionWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    item: str
    frequency: int
    chapters: list[int]
    note: str


def assess_repetition(
    *,
    prose: str,
    chapter_number: int,
    location: str,
    conflict: str,
    history: StyleHistory,
    watchlist: list[str],
    recent_window: int = 3,
) -> list[RepetitionWarning]:
    """Frequency-aware checks. Phrases are never permanently banned."""

    warnings: list[RepetitionWarning] = []
    recent = range(max(1, chapter_number - recent_window), chapter_number)
    lowered = prose.lower()

    for phrase in watchlist:
        key = _norm(phrase)
        if not key:
            continue
        in_current = key in _norm(prose) or phrase.lower() in lowered
        prior = [n for n in history.phrases.get(key, []) if n in recent]
        if in_current and len(prior) >= 2:
            warnings.append(
                RepetitionWarning(
                    category="phrase",
                    item=phrase,
                    frequency=len(prior) + 1,
                    chapters=[*prior, chapter_number],
                    note="Repeated in recent chapters; vary the beat instead of banning the phrase.",
                )
            )

    scene_key = f"{_norm(location)}|{_norm(conflict)[:48]}"
    scene_prior = [n for n in history.scene_patterns.get(scene_key, []) if n < chapter_number]
    if len(scene_prior) >= 2:
        warnings.append(
            RepetitionWarning(
                category="scene_pattern",
                item=scene_key,
                frequency=len(scene_prior) + 1,
                chapters=scene_prior,
                note="Similar location-and-conflict shape is repeating.",
            )
        )

    conflict_key = _norm(conflict)[:80]
    conflict_prior = [n for n in history.conflicts.get(conflict_key, []) if n < chapter_number]
    if conflict_key and len(conflict_prior) >= 2:
        warnings.append(
            RepetitionWarning(
                category="conflict",
                item=conflict,
                frequency=len(conflict_prior) + 1,
                chapters=conflict_prior,
                note="Conflict fingerprint is repeating; escalate or invert the pressure.",
            )
        )

    for quote in _QUOTED.findall(prose):
        key = _norm(quote)
        if not key:
            continue
        prior = [n for n in history.dialogue_patterns.get(key, []) if n in recent]
        if len(prior) >= 1 and key in { _norm(item) for item in watchlist }:
            warnings.append(
                RepetitionWarning(
                    category="dialogue",
                    item=quote,
                    frequency=len(prior) + 1,
                    chapters=[*prior, chapter_number],
                    note="Watched dialogue pattern is repeating in the recent window.",
                )
            )
    return warnings


def record_chapter(
    history: StyleHistory,
    *,
    chapter_number: int,
    prose: str,
    location: str,
    conflict: str,
    watchlist: list[str],
) -> None:
    for phrase in watchlist:
        key = _norm(phrase)
        if key and (key in _norm(prose) or phrase.lower() in prose.lower()):
            if chapter_number not in history.phrases[key]:
                history.phrases[key].append(chapter_number)
    for gram in _ngrams(prose, 5)[:40]:
        if chapter_number not in history.phrases[gram]:
            history.phrases[gram].append(chapter_number)
    scene_key = f"{_norm(location)}|{_norm(conflict)[:48]}"
    if chapter_number not in history.scene_patterns[scene_key]:
        history.scene_patterns[scene_key].append(chapter_number)
    conflict_key = _norm(conflict)[:80]
    if conflict_key and chapter_number not in history.conflicts[conflict_key]:
        history.conflicts[conflict_key].append(chapter_number)
    for quote in _QUOTED.findall(prose):
        key = _norm(quote)
        if key and chapter_number not in history.dialogue_patterns[key]:
            history.dialogue_patterns[key].append(chapter_number)
