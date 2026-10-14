from __future__ import annotations

from collections.abc import Iterable

from novel_engine.agents.contracts import ContinuityFinding
from novel_engine.models.enums import ContinuityVerdict


def scan_plot_thread_lifecycle(
    *,
    hooks: Iterable[object],
    foreshadowings: Iterable[object],
    chapter_numbers: dict[object, int] | None = None,
    latest_approved_chapter: int = 0,
) -> list[ContinuityFinding]:
    """Validate setup/payoff state for long-running plot threads."""
    chapter_map = chapter_numbers or {}
    findings: list[ContinuityFinding] = []
    for item in hooks:
        status = _value(getattr(item, "status", ""))
        setup = _chapter_map(item, "setup_chapter_id", chapter_map)
        resolved = _chapter_map(item, "resolved_chapter_id", chapter_map)
        description = str(getattr(item, "description", "") or "")[:120]
        if status in {"planted", "active", "resolved"} and setup is None:
            findings.append(_finding("hook_setup_missing", "ERROR", f"钩子“{description}”没有埋设章节。"))
        if status == "resolved" and resolved is None:
            findings.append(_finding("hook_resolution_missing", "ERROR", f"钩子“{description}”标记已解决但没有回收章节。"))
        if resolved is not None and setup is not None and resolved < setup:
            findings.append(_finding("hook_resolution_order", "ERROR", f"钩子“{description}”的回收章节早于埋设章节。"))
        if resolved is not None and resolved > latest_approved_chapter:
            findings.append(_finding("hook_resolution_future", "WARNING", f"钩子“{description}”指向尚未确认的第 {resolved} 章。"))

    for item in foreshadowings:
        status = _value(getattr(item, "status", ""))
        setup = _chapter_map(item, "setup_chapter_id", chapter_map)
        expected = _chapter_map(item, "expected_payoff_chapter_id", chapter_map)
        actual = _chapter_map(item, "actual_payoff_chapter_id", chapter_map)
        description = str(getattr(item, "description", "") or "")[:120]
        if status in {"planted", "paid_off", "missed"} and setup is None:
            findings.append(_finding("foreshadow_setup_missing", "ERROR", f"伏笔“{description}”没有埋设章节。"))
        if status == "paid_off" and actual is None:
            findings.append(_finding("foreshadow_payoff_missing", "ERROR", f"伏笔“{description}”标记已回收但没有实际回收章节。"))
        if actual is not None and status != "paid_off":
            findings.append(_finding("foreshadow_payoff_status_mismatch", "ERROR", f"伏笔“{description}”有实际回收章节但状态不是 paid_off。"))
        if expected is not None and setup is not None and expected < setup:
            findings.append(_finding("foreshadow_payoff_order", "ERROR", f"伏笔“{description}”的预计回收章节早于埋设章节。"))
        if expected is not None and expected <= latest_approved_chapter and status not in {"paid_off", "missed", "dropped"}:
            findings.append(_finding("foreshadow_overdue", "WARNING", f"伏笔“{description}”已超过预计回收章节第 {expected} 章，仍未回收。"))
    return findings


def _chapter_map(item: object, field: str, mapping: dict[object, int]) -> int | None:
    value = getattr(item, field, None)
    return mapping.get(value) if value is not None else None


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _finding(category: str, severity: str, problem: str) -> ContinuityFinding:
    return ContinuityFinding(
        severity=ContinuityVerdict.ERROR if severity == "ERROR" else ContinuityVerdict.WARNING,
        category=category,
        problem=problem,
        evidence=category,
        recommendation="检查钩子/伏笔的埋设、预计回收和实际回收章节。",
    )
