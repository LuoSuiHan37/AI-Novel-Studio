from __future__ import annotations

from novel_engine.agents.contracts import ContinuityFinding
from novel_engine.models.enums import ContinuityVerdict
from novel_engine.presets.models import ContinuitySignal


def scan_continuity_signals(
    *,
    prose: str,
    world_rules: list[str],
    signals: list[ContinuitySignal],
) -> list[ContinuityFinding]:
    """Preset-driven canon flags. Core engine has no AlphaNovel-specific strings."""

    lowered = prose.lower()
    findings: list[ContinuityFinding] = []
    for signal in signals:
        needle = signal.rule_contains.lower()
        matching_rules = [rule for rule in world_rules if needle in rule.lower()]
        if not matching_rules:
            continue
        hit = next((phrase for phrase in signal.error_if_prose_contains if phrase.lower() in lowered), None)
        if not hit:
            continue
        excused = any(token.lower() in lowered for token in signal.unless_prose_contains)
        if excused:
            continue
        findings.append(
            ContinuityFinding(
                severity=ContinuityVerdict.ERROR,
                category="world_rule",
                problem=f"Prose may break a hard rule related to '{signal.rule_contains}'",
                evidence=hit,
                recommendation="Revise so the world rule still holds, or show the allowed exception.",
            )
        )
    return findings
