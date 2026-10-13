from __future__ import annotations

import re

from novel_engine.agents.contracts import ContinuityFinding, WriterContext
from novel_engine.models.enums import ContinuityVerdict
from novel_engine.style.word_count import count_text_units


_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b")


def scan_context_alignment(*, prose: str, context: WriterContext) -> list[ContinuityFinding]:
    """Cheap, deterministic checks for catastrophic chapter/context mismatches.

    The LLM remains responsible for meaning and subtle continuity. These checks are
    deliberately conservative: they only emit ERROR for failures that are strong
    evidence the generated chapter belongs to another story.
    """
    findings: list[ContinuityFinding] = []
    expected: set[str] = set()
    for item in context.characters:
        for raw_name in [item.name, *item.aliases]:
            name = raw_name.strip()
            if name:
                expected.add(name.casefold())
    planned = {item.strip().casefold() for item in context.chapter_plan.characters if item.strip()}
    expected |= planned
    lowered = prose.casefold()
    present_expected = {name for name in expected if name in lowered}

    if expected and not present_expected:
        unknown_names = _unknown_names(prose, expected)
        if len(unknown_names) >= 2:
            findings.append(
                ContinuityFinding(
                    severity=ContinuityVerdict.ERROR,
                    category="story_context_mismatch",
                    problem="The chapter contains none of the planned/known characters and appears to belong to another story.",
                    evidence="Unknown named entities: " + ", ".join(sorted(unknown_names)[:8]),
                    recommendation="Regenerate the chapter using the approved story bible and chapter plan.",
                )
            )
        else:
            findings.append(
                ContinuityFinding(
                    severity=ContinuityVerdict.WARNING,
                    category="character_presence",
                    problem="None of the planned or known character names appear in the chapter.",
                    evidence="Expected: " + ", ".join(sorted(expected)[:8]),
                    recommendation="Verify that the chapter uses the approved POV and character roster.",
                )
            )

    previous = context.previous_chapter_summary.strip()
    if previous and len(prose.strip()) < 120:
        findings.append(
            ContinuityFinding(
                severity=ContinuityVerdict.WARNING,
                category="chapter_completeness",
                problem="The generated chapter is unusually short for a continuation chapter.",
                evidence=f"{count_text_units(prose)} counted units; previous chapter context was supplied.",
                recommendation="Regenerate or review the chapter for truncated output.",
            )
        )
    return findings


def _unknown_names(prose: str, expected: set[str]) -> set[str]:
    names: set[str] = set()
    for match in _NAME_RE.finditer(prose):
        candidate = match.group(0).strip()
        if candidate.casefold() in expected:
            continue
        # Sentence-initial common words are not useful entity evidence.
        if candidate.casefold() in {"The", "A", "An", "But", "Then", "He", "She", "It", "I"}:
            continue
        names.add(candidate)
    return names
