from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field


_TOKEN = re.compile(r"[a-z']+|[\u3400-\u9fff]")


def _norm(value: object) -> str:
    return " ".join(_TOKEN.findall(str(value or "").casefold()))


def _field(item: object, name: str) -> str:
    return _norm(getattr(item, name, ""))


class NarrativeHistory(BaseModel):
    """Persisted, explainable fingerprints of chapter-level story patterns."""

    model_config = ConfigDict(extra="forbid")

    fingerprints: dict[str, list[int]] = Field(default_factory=lambda: defaultdict(list))
    endings: dict[str, list[int]] = Field(default_factory=lambda: defaultdict(list))

    def model_post_init(self, _context) -> None:
        self.fingerprints = defaultdict(list, self.fingerprints)
        self.endings = defaultdict(list, self.endings)


class NarrativeWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    item: str
    frequency: int
    chapters: list[int]
    note: str


def fingerprint_for_plan(*, location: str, conflict: str, scenes: Iterable[object]) -> str:
    """Build a deterministic chapter fingerprint from approved planning data."""

    scene_parts: list[str] = []
    for scene in sorted(scenes, key=lambda item: int(getattr(item, "scene_number", 0))):
        scene_parts.append(
            ":".join(
                (
                    _field(scene, "location"),
                    _field(scene, "goal"),
                    _field(scene, "conflict"),
                    _field(scene, "turning_point"),
                    _field(scene, "information_revealed"),
                    _field(scene, "ending"),
                )
            )
        )
    return "|".join((_norm(location), _norm(conflict), "||".join(scene_parts)))


def ending_for_plan(*, cliffhanger: str, scenes: Iterable[object]) -> str:
    ordered = sorted(scenes, key=lambda item: int(getattr(item, "scene_number", 0)))
    ending = getattr(ordered[-1], "ending", "") if ordered else ""
    return _norm(ending or cliffhanger)


def assess_narrative_repetition(
    *,
    chapter_number: int,
    location: str,
    conflict: str,
    cliffhanger: str,
    scenes: Iterable[object],
    history: NarrativeHistory,
    recent_window: int = 6,
) -> list[NarrativeWarning]:
    fingerprint = fingerprint_for_plan(location=location, conflict=conflict, scenes=scenes)
    ending = ending_for_plan(cliffhanger=cliffhanger, scenes=scenes)
    recent = range(max(1, chapter_number - recent_window), chapter_number)
    warnings: list[NarrativeWarning] = []

    prior = [n for n in history.fingerprints.get(fingerprint, []) if n in recent]
    if fingerprint and prior:
        warnings.append(
            NarrativeWarning(
                category="narrative_pattern",
                item=fingerprint,
                frequency=len(prior) + 1,
                chapters=[*prior, chapter_number],
                note="The approved scene/goal/conflict/turning-point shape repeats in the recent window; vary the pressure or outcome.",
            )
        )

    ending_prior = [n for n in history.endings.get(ending, []) if n in recent]
    if ending and len(ending_prior) >= 2:
        warnings.append(
            NarrativeWarning(
                category="chapter_ending_pattern",
                item=ending,
                frequency=len(ending_prior) + 1,
                chapters=[*ending_prior, chapter_number],
                note="The chapter-ending function repeats too often; use a different consequence, decision, discovery, or pressure point.",
            )
        )
    return warnings


def record_narrative_plan(
    history: NarrativeHistory,
    *,
    chapter_number: int,
    location: str,
    conflict: str,
    cliffhanger: str,
    scenes: Iterable[object],
) -> None:
    fingerprint = fingerprint_for_plan(location=location, conflict=conflict, scenes=scenes)
    ending = ending_for_plan(cliffhanger=cliffhanger, scenes=scenes)
    if fingerprint and chapter_number not in history.fingerprints[fingerprint]:
        history.fingerprints[fingerprint].append(chapter_number)
    if ending and chapter_number not in history.endings[ending]:
        history.endings[ending].append(chapter_number)
