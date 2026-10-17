from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novel_engine.models.enums import ContinuityVerdict


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def status(self) -> str:
        return "passed" if self.passed else "blocked"


def _blocked(check: Any) -> bool:
    return bool(check and getattr(check, "blocked", False))


def evaluate_chapter_quality(
    *,
    continuity: Any,
    editor: Any,
    length_ok: bool,
    repetition_check: dict | None,
    relevance_check: dict | None,
    sequence_review: list[Any] | None,
    commercial: Any | None = None,
    require_independent_review: bool = False,
) -> QualityGateResult:
    """Single source of truth for whether a draft may be promoted.

    Saving a draft remains allowed, but promotion to canon/approved is not.
    This deliberately treats structural sequence and reveal violations as
    blocking: a warning that is ignored is not a quality gate.
    """

    reasons: list[str] = []
    warnings: list[str] = []
    if continuity is None or continuity.overall is ContinuityVerdict.ERROR:
        reasons.append("continuity_error")
    if editor is None or bool(getattr(editor, "needs_human_review", False)):
        reasons.append("editor_requires_review")
    if not length_ok:
        reasons.append("length_out_of_range")
    if _blocked(repetition_check) or _blocked(relevance_check):
        reasons.append("chapter_check_blocked")
    for item in sequence_review or []:
        category = str(getattr(item, "category", "sequence"))
        if category in {
            "repeated_character_behavior",
            "repeated_ending",
            "repeated_opening",
            "repeated_reveal",
            "reveal_budget",
            "narrative_pattern",
            "chapter_ending_pattern",
        }:
            reasons.append(category)
        else:
            warnings.append(category)
    if require_independent_review and commercial is None:
        reasons.append("independent_review_missing")
    if commercial is not None:
        for name in ("reader_pressure_score", "reader_promise_score", "rhythm_score"):
            if float(getattr(commercial, name, 0) or 0) < 6:
                reasons.append(f"commercial_{name}_low")
        if float(getattr(commercial, "ai_style_risk_score", 0) or 0) < 5:
            reasons.append("commercial_ai_style_risk")
    return QualityGateResult(
        passed=not reasons,
        blocking_reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
    )
