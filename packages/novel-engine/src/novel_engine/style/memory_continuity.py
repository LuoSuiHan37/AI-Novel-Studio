from __future__ import annotations

import re

from novel_engine.agents.contracts import ContinuityFinding, SceneHandoff
from novel_engine.models.enums import ContinuityVerdict


def scan_scene_handoffs(
    *,
    prose: str,
    handoffs: list[SceneHandoff],
    planned_scene_numbers: set[int] | None = None,
    planned_scene_locations: dict[int, str] | None = None,
    planned_scene_characters: dict[int, set[str]] | None = None,
    allowed_characters: set[str] | None = None,
) -> list[ContinuityFinding]:
    """Validate durable scene state without pretending to understand all prose semantics.

    These checks are intentionally conservative. They catch malformed memory and
    obvious evidence/knowledge contradictions while leaving literary judgment to
    the continuity agent and human approval.
    """
    findings: list[ContinuityFinding] = []
    planned = planned_scene_numbers or set()
    locations = planned_scene_locations or {}
    scene_characters = planned_scene_characters or {}
    allowed = {item.casefold() for item in (allowed_characters or set()) if item.strip()}
    seen: set[int] = set()
    prose_folded = prose.casefold()

    if not handoffs:
        findings.append(
            ContinuityFinding(
                severity=ContinuityVerdict.WARNING,
                category="scene_handoff_missing",
                problem="No scene handoffs were extracted for the approved chapter.",
                evidence="scene_handoffs=[]",
                recommendation="Regenerate the summary or add handoffs before relying on scene-level memory.",
            )
        )
        return findings

    handoff_numbers = {item.scene_number for item in handoffs}
    if planned:
        missing = sorted(planned - handoff_numbers)
        if missing:
            findings.append(
                _finding(
                    "scene_handoff_missing_scene",
                    "ERROR",
                    "缺少场景交接：" + ", ".join(str(item) for item in missing),
                )
            )

    for handoff in handoffs:
        number = handoff.scene_number
        if number in seen:
            findings.append(_finding("scene_handoff_duplicate", "ERROR", f"Scene {number} has duplicate handoffs."))
        seen.add(number)
        if planned and number not in planned:
            findings.append(
                _finding(
                    "scene_handoff_scene_mismatch",
                    "ERROR",
                    f"Scene {number} is not present in the approved chapter plan.",
                )
            )
        if not handoff.what_happened.strip():
            findings.append(_finding("scene_handoff_empty", "ERROR", f"Scene {number} has no event summary."))
        expected_location = locations.get(number, "").strip().casefold()
        actual_location = handoff.location.strip().casefold()
        if expected_location and actual_location and expected_location != actual_location:
            findings.append(
                _finding(
                    "scene_handoff_location_mismatch",
                    "WARNING",
                    f"Scene {number} handoff location differs from the approved scene plan.",
                    evidence=f"planned={locations.get(number)}; handoff={handoff.location}",
                )
            )
        planned_names = {item.casefold() for item in scene_characters.get(number, set())}
        if planned_names:
            referenced_names = {name.casefold() for name in [*handoff.who_knows, *handoff.unknown_to]}
            for name in sorted(referenced_names - planned_names):
                findings.append(
                    _finding(
                        "scene_handoff_character_mismatch",
                        "WARNING",
                        f"Scene {number} knowledge state references '{name}', not listed in the scene plan.",
                    )
                )

        if handoff.source_excerpt.strip():
            excerpt = _normalize(handoff.source_excerpt)
            if excerpt and excerpt not in _normalize(prose):
                overlap = _token_overlap(excerpt, prose_folded)
                if overlap < 0.45:
                    findings.append(
                        _finding(
                            "scene_handoff_evidence_missing",
                            "WARNING",
                            f"Scene {number} source excerpt is not found in the approved prose.",
                            evidence=handoff.source_excerpt[:240],
                        )
                    )

        for field_name, mapping in (("who_knows", handoff.who_knows), ("unknown_to", handoff.unknown_to)):
            for character, facts in mapping.items():
                if allowed and character.casefold() not in allowed:
                    findings.append(
                        _finding(
                            "scene_handoff_unknown_character",
                            "WARNING",
                            f"{field_name} references character '{character}', not in the approved roster.",
                        )
                    )
                if not facts:
                    findings.append(
                        _finding(
                            "scene_handoff_empty_knowledge",
                            "WARNING",
                            f"{field_name}.{character} is empty.",
                        )
                    )

        overlap_keys = set(handoff.who_knows).intersection(handoff.unknown_to)
        for character in overlap_keys:
            known = {item.casefold() for item in handoff.who_knows[character]}
            unknown = {item.casefold() for item in handoff.unknown_to[character]}
            contradiction = known.intersection(unknown)
            if contradiction:
                findings.append(
                    _finding(
                        "scene_handoff_knowledge_contradiction",
                        "ERROR",
                        f"Character '{character}' is both told and not told the same fact.",
                        evidence="; ".join(sorted(contradiction)[:3]),
                    )
                )
    return findings


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _token_overlap(excerpt: str, prose: str) -> float:
    tokens = set(re.findall(r"[\w\u3400-\u9fff]{2,}", excerpt))
    if not tokens:
        return 1.0
    present = sum(token in prose for token in tokens)
    return present / len(tokens)


def _finding(category: str, severity: str, problem: str, evidence: str = "") -> ContinuityFinding:
    verdict = ContinuityVerdict.ERROR if severity == "ERROR" else ContinuityVerdict.WARNING
    return ContinuityFinding(
        severity=verdict,
        category=category,
        problem=problem,
        evidence=evidence or category,
        recommendation="Review the chapter summary and scene handoff before approval.",
    )
