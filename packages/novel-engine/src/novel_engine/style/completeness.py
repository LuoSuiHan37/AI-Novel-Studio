from __future__ import annotations

from novel_engine.agents.contracts import ContinuityFinding
from novel_engine.models.enums import ContinuityVerdict


_CLOSERS = "\"'”’）)]}》」』"
_END_PUNCTUATION = "。！？.!?…"


def scan_prose_completeness(prose: str) -> list[ContinuityFinding]:
    """Detect cheap, high-confidence signs that a generated prose body was cut off."""
    text = prose.strip()
    if not text:
        return []

    findings: list[ContinuityFinding] = []
    if _unbalanced_pairs(text):
        findings.append(_finding(
            "The prose contains an unbalanced quote or bracket and may be truncated.",
            "paired quote/bracket delimiters are not balanced",
            "Regenerate or repair the complete sentence and close the dialogue or bracket.",
        ))

    terminal = text.rstrip(_CLOSERS).rstrip()
    if terminal and terminal[-1] not in _END_PUNCTUATION:
        findings.append(_finding(
            "The prose does not end at a sentence boundary and may be truncated.",
            f"last non-closing character: {terminal[-1]!r}",
            "Finish the current sentence or scene before saving or approving the chapter.",
        ))
    return findings


def escalate_verdict(base: ContinuityVerdict, findings: list[ContinuityFinding]) -> ContinuityVerdict:
    """Ensure deterministic ERROR findings cannot be hidden by a model's PASS verdict."""
    if any(item.severity is ContinuityVerdict.ERROR for item in findings):
        return ContinuityVerdict.ERROR
    if base is ContinuityVerdict.ERROR:
        return base
    if any(item.severity is ContinuityVerdict.WARNING for item in findings):
        return ContinuityVerdict.WARNING
    return base


def _unbalanced_pairs(text: str) -> bool:
    pairs = {"（": "）", "(": ")", "[": "]", "{": "}", "「": "」", "『": "』"}
    stack: list[str] = []
    for char in text:
        if char in pairs:
            stack.append(pairs[char])
        elif char in pairs.values():
            if not stack or stack.pop() != char:
                return True
    return bool(stack)


def _finding(problem: str, evidence: str, recommendation: str) -> ContinuityFinding:
    return ContinuityFinding(
        severity=ContinuityVerdict.ERROR,
        category="prose_completeness",
        problem=problem,
        evidence=evidence,
        recommendation=recommendation,
    )
