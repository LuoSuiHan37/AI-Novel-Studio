from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def _signal(*, owner: str, category: str, message: str, evidence: str, severity: str, chapter_number: int | None = None) -> dict:
    return {
        "owner": owner,
        "category": category,
        "message": message,
        "evidence": evidence,
        "severity": severity,
        "chapter_number": chapter_number,
    }


def chapter_optimization_signals(*, chapter_number: int, audit: dict, editor: object | None, commercial: dict | None) -> list[dict]:
    signals: list[dict] = []
    length = audit.get("length_check") or {}
    if length and not length.get("ok", True):
        signals.append(_signal(
            owner="writer_prompt", category="length", severity="ERROR", chapter_number=chapter_number,
            message="正文长度没有稳定落在平台范围内。",
            evidence=f"实际 {length.get('count', '?')}，目标 {length.get('minimum', '?')}-{length.get('maximum', '?')}。",
        ))
    repetition = audit.get("repetition_check") or {}
    if repetition.get("blocked"):
        signals.append(_signal(
            owner="writer_prompt", category="repetition", severity="ERROR", chapter_number=chapter_number,
            message="章节触发了重复表达或重复情节检查。",
            evidence=str(repetition.get("matches", [])[:2]),
        ))
    relevance = audit.get("relevance_check") or {}
    if relevance.get("blocked"):
        signals.append(_signal(
            owner="chapter_plan", category="relevance", severity="ERROR", chapter_number=chapter_number,
            message="正文没有充分执行当前章节计划。",
            evidence=str(relevance.get("missing_requirements", [])[:4]),
        ))
    if editor is not None:
        for name in ("pacing", "dialogue", "emotion", "character_voice", "repetition", "hook_strength", "plot_progress"):
            dimension = getattr(editor, name, None)
            if dimension is not None and getattr(dimension, "score", 10) < 6:
                signals.append(_signal(
                    owner="writer_prompt", category=name, severity="WARNING", chapter_number=chapter_number,
                    message=f"Editor 对 {name} 的评分低于 6。",
                    evidence=getattr(dimension, "notes", ""),
                ))
    if commercial:
        for score_name, category in (("reader_pressure_score", "reader_pressure"), ("reader_promise_score", "reader_promise"), ("rhythm_score", "rhythm"), ("ai_style_risk_score", "ai_style_risk")):
            score = commercial.get(score_name)
            if isinstance(score, int) and score < 6:
                signals.append(_signal(
                    owner="writer_prompt", category=category, severity="WARNING", chapter_number=chapter_number,
                    message=f"独立审核的 {category} 评分偏低。",
                    evidence=f"{score_name}={score}/10",
                ))
        for finding in commercial.get("findings", [])[:8]:
            text = str(finding)
            lowered = text.lower()
            owner = "chapter_plan" if any(word in lowered for word in ("plan", "scene", "planned", "场景", "计划")) else "writer_prompt"
            category = "scene_execution" if owner == "chapter_plan" else "prose_quality"
            signals.append(_signal(owner=owner, category=category, severity="WARNING", chapter_number=chapter_number, message="独立审核发现重复问题。", evidence=text))
    return signals


def optimization_report(reviews: Iterable[dict]) -> dict:
    signals = [signal for review in reviews for signal in (review.get("optimization_signals") or [])]
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for signal in signals:
        grouped[(signal.get("owner", "unknown"), signal.get("category", "unknown"))].append(signal)
    clusters = []
    for (owner, category), items in sorted(grouped.items(), key=lambda pair: len(pair[1]), reverse=True):
        chapters = sorted({item.get("chapter_number") for item in items if item.get("chapter_number") is not None})
        if owner == "writer_prompt":
            recommendation = f"检查 Writer Prompt 的 {category} 约束，并用真实章节样本创建新版本后回归比较。"
        elif owner == "chapter_plan":
            recommendation = "先检查章节计划是否具体、可执行，再决定是否调整 Prompt；不要把计划问题全部归因于模型。"
        else:
            recommendation = "检查对应审核规则和上下文输入，确认这是模型问题还是检查误报。"
        clusters.append({"owner": owner, "category": category, "count": len(items), "chapters": chapters, "recommendation": recommendation, "examples": items[:3]})
    return {"total_signals": len(signals), "signals": signals[-100:], "clusters": clusters[:20]}
