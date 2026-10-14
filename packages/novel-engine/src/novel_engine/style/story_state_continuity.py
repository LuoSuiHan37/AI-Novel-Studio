from __future__ import annotations

import re
from collections.abc import Iterable

from novel_engine.agents.contracts import ContinuityFinding
from novel_engine.models.enums import ContinuityVerdict


def scan_story_state_continuity(
    *,
    chapters: Iterable[object],
    plans: dict[int, object] | None = None,
    arcs: Iterable[object] = (),
    plot_beats: Iterable[object] = (),
    timeline_events: Iterable[object] = (),
    memory_rows: Iterable[object] = (),
) -> list[ContinuityFinding]:
    """Check persistent plot, timeline, and character-state contracts."""
    ordered = sorted(chapters, key=lambda item: int(getattr(item, "chapter_number", 0)))
    plan_map = plans or {}
    findings: list[ContinuityFinding] = []
    approved_numbers = {
        int(getattr(item, "chapter_number", 0))
        for item in ordered
        if str(getattr(getattr(item, "status", None), "value", getattr(item, "status", ""))) in {"approved", "published"}
    }

    # A changed location or cast is allowed, but an approved chapter must have
    # a plan that records that change; otherwise later retrieval cannot explain
    # the transition.
    for chapter in ordered:
        number = int(getattr(chapter, "chapter_number", 0))
        if number not in approved_numbers:
            continue
        plan = plan_map.get(number)
        if plan is None:
            continue
        if not str(getattr(plan, "location", "") or "").strip():
            findings.append(_finding("chapter_location_missing", "ERROR", f"第 {number} 章计划没有地点。"))
        if not list(getattr(plan, "characters", []) or []):
            findings.append(_finding("chapter_characters_missing", "ERROR", f"第 {number} 章计划没有人物。"))

    # Timeline records must be unique and monotonic. The database has a unique
    # constraint, but this also catches imported or legacy data before publish.
    sequences: list[int] = []
    for event in timeline_events:
        sequence = getattr(event, "sequence", None)
        if sequence is None:
            findings.append(_finding("timeline_sequence_missing", "ERROR", "存在没有 sequence 的时间线事件。"))
            continue
        sequences.append(int(sequence))
    duplicates = sorted({item for item in sequences if sequences.count(item) > 1})
    if duplicates:
        findings.append(_finding("timeline_sequence_duplicate", "ERROR", f"时间线 sequence 重复：{duplicates}。"))
    if sequences != sorted(sequences):
        findings.append(_finding("timeline_sequence_order", "WARNING", "时间线事件返回顺序不是递增顺序。"))

    # A hinted plot beat should leave textual evidence once its hinted chapter
    # has been approved. This is a warning because a beat may be fulfilled by
    # synonyms that require human/LLM review.
    summaries = _chapter_text(memory_rows)
    for beat in plot_beats:
        hint = getattr(beat, "chapter_hint", None)
        if hint is None or int(hint) not in approved_numbers:
            continue
        description = f"{getattr(beat, 'name', '')} {getattr(beat, 'description', '')}".strip()
        tokens = _meaningful_tokens(description)
        evidence = summaries.get(int(hint), "").casefold()
        if tokens and sum(token in evidence for token in tokens) / len(tokens) < 0.35:
            findings.append(
                _finding(
                    "plot_beat_evidence_missing",
                    "WARNING",
                    f"主线节点“{getattr(beat, 'name', '未命名')}”标记在第 {hint} 章，但章节记忆中缺少明显证据。",
                    evidence=description[:240],
                )
            )

    # Knowledge boundaries cannot assert the same fact for both sides after
    # durable merge. This is a database-level safety net in addition to the
    # per-scene validator.
    for row in memory_rows:
        known = {str(item).casefold() for item in (getattr(row, "known_by", None) or [])}
        unknown = {str(item).casefold() for item in (getattr(row, "unknown_to", None) or [])}
        if known.intersection(unknown):
            findings.append(
                _finding(
                    "persistent_knowledge_contradiction",
                    "ERROR",
                    f"记忆事实“{getattr(row, 'content', '')[:80]}”同时包含已知和未知人物。",
                    evidence=", ".join(sorted(known.intersection(unknown))),
                )
            )
    return findings


def _chapter_text(rows: Iterable[object]) -> dict[int, str]:
    output: dict[int, str] = {}
    for row in rows:
        number = getattr(row, "chapter_number", None)
        if number is None:
            continue
        metadata = getattr(row, "extra_metadata", None) or {}
        if metadata.get("kind") == "chapter_memory":
            output[int(number)] = str(getattr(row, "content", "") or "")
    return output


def _meaningful_tokens(value: str) -> list[str]:
    return [item for item in re.findall(r"[a-zA-Z\u3400-\u9fff]{3,}", value.casefold()) if item not in {"the", "and", "with", "chapter"}]


def _finding(category: str, severity: str, problem: str, evidence: str = "") -> ContinuityFinding:
    return ContinuityFinding(
        severity=ContinuityVerdict.ERROR if severity == "ERROR" else ContinuityVerdict.WARNING,
        category=category,
        problem=problem,
        evidence=evidence or category,
        recommendation="检查章节计划、时间线、主线节点和人物认知记录。",
    )
