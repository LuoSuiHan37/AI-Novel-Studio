from __future__ import annotations

from collections.abc import Iterable

from novel_engine.agents.contracts import ContinuityFinding
from novel_engine.models.enums import ContinuityVerdict


def scan_longitudinal_continuity(
    *,
    chapters: Iterable[object],
    chapter_memories: dict[int, dict] | None = None,
    target_chapter_count: int | None = None,
) -> list[ContinuityFinding]:
    """Audit continuity prerequisites across the whole manuscript.

    This is deliberately deterministic and evidence-based. It does not claim to
    infer literary causality; it reports missing durable state and handoff
    contract breaks that must be reviewed before a long novel is published.
    """
    ordered = sorted(chapters, key=lambda item: int(getattr(item, "chapter_number", 0)))
    findings: list[ContinuityFinding] = []
    memories = chapter_memories or {}
    numbers = [int(getattr(item, "chapter_number", 0)) for item in ordered]
    seen: set[int] = set()
    for number in numbers:
        if number in seen:
            findings.append(_finding("duplicate_chapter_number", "ERROR", f"第 {number} 章出现重复记录。"))
        seen.add(number)

    if numbers:
        upper = target_chapter_count or max(numbers)
        missing = [number for number in range(1, upper + 1) if number not in seen]
        if missing:
            findings.append(
                _finding(
                    "chapter_sequence_gap",
                    "WARNING",
                    f"章节序列存在缺口：{_compact_numbers(missing)}。",
                )
            )

    for chapter in ordered:
        number = int(getattr(chapter, "chapter_number", 0))
        status = str(getattr(getattr(chapter, "status", None), "value", getattr(chapter, "status", "")))
        approved = status in {"approved", "published"}
        content = str(getattr(chapter, "content", "") or "").strip()
        memory = memories.get(number)
        if approved and not content:
            findings.append(_finding("approved_empty_chapter", "ERROR", f"第 {number} 章已确认但正文为空。"))
        if approved and memory is None:
            findings.append(
                _finding(
                    "chapter_memory_missing",
                    "WARNING",
                    f"第 {number} 章已确认，但没有结构化章节记忆，请执行历史回填。",
                )
            )
        if memory is None:
            continue
        if not str(memory.get("summary") or "").strip():
            findings.append(_finding("chapter_memory_empty", "ERROR", f"第 {number} 章的章节摘要为空。"))

        next_chapter = next((item for item in ordered if int(getattr(item, "chapter_number", 0)) == number + 1), None)
        if next_chapter is None or not str(getattr(next_chapter, "content", "") or "").strip():
            continue
        next_text = str(getattr(next_chapter, "content", "") or "").casefold()
        for handoff in memory.get("scene_handoffs") or []:
            requirements = [str(item).strip() for item in handoff.get("next_scene_requirements") or [] if str(item).strip()]
            for requirement in requirements:
                tokens = [token.casefold() for token in requirement.split() if len(token) > 2]
                present_ratio = (
                    sum(token in next_text for token in tokens) / len(tokens)
                    if tokens
                    else 1.0
                )
                if tokens and present_ratio < 0.5:
                    findings.append(
                        _finding(
                            "handoff_not_observed_next_chapter",
                            "WARNING",
                            f"第 {number} 章场景 {handoff.get('scene_number', '?')} 的下一场要求，未在第 {number + 1} 章正文中找到明显证据。",
                            evidence=requirement[:240],
                        )
                    )
    return findings


def _finding(category: str, severity: str, problem: str, evidence: str = "") -> ContinuityFinding:
    return ContinuityFinding(
        severity=ContinuityVerdict.ERROR if severity == "ERROR" else ContinuityVerdict.WARNING,
        category=category,
        problem=problem,
        evidence=evidence or category,
        recommendation="检查章节状态、结构化记忆和下一章承接内容。",
    )


def _compact_numbers(numbers: list[int]) -> str:
    return ", ".join(str(item) for item in numbers[:20]) + (" …" if len(numbers) > 20 else "")
