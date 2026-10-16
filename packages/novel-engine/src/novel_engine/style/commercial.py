from __future__ import annotations

import re

from novel_engine.agents.contracts import ContinuityFinding, WriterContext
from novel_engine.models.enums import ContinuityVerdict
from novel_engine.style.word_count import count_text_units


_TEMPLATE_PHRASES = (
    "she did not know that",
    "little did she know",
    "what she did not know",
    "the truth was",
    "he could not know",
    "everything was about to change",
)


def scan_commercial_quality(*, prose: str, context: WriterContext) -> list[ContinuityFinding]:
    """Conservative, local checks for reader pressure and obvious AI patterns.

    Meaning and literary quality stay with the Editor Agent. These checks only
    block truncation or a missing chapter contract and warn on strong templates.
    """
    plan = context.chapter_plan
    findings: list[ContinuityFinding] = []
    words = count_text_units(prose)
    profile = context.creative_profile if isinstance(context.creative_profile, dict) else {}
    contract = context.creative_contract if isinstance(context.creative_contract, dict) else {}

    if not prose.strip():
        findings.append(_finding(
            ContinuityVerdict.ERROR,
            "commercial_contract",
            "Chapter prose is empty.",
            "0 words",
            "Generate or restore a non-empty chapter before review.",
        ))
        return findings

    # A very short continuation is almost always truncation, not an artistic
    # choice. The platform range remains a warning at the higher level.
    if words < context.chapter_word_min:
        findings.append(_finding(
            ContinuityVerdict.ERROR,
            "chapter_length",
            "Chapter is shorter than the platform minimum.",
            f"{words} counted units; minimum is {context.chapter_word_min}",
            "Regenerate or revise the chapter until it reaches the platform minimum.",
        ))
    if words > context.chapter_word_max:
        findings.append(_finding(
            ContinuityVerdict.ERROR,
            "chapter_length",
            "Chapter exceeds the platform maximum.",
            f"{words} counted units; maximum is {context.chapter_word_max}",
            "Compress repeated description, exposition, and secondary beats; finish the current scene without cutting a sentence or leaving a scene unfinished.",
        ))

    if plan.characters and not any(name.casefold() in prose.casefold() for name in plan.characters):
        findings.append(_finding(
            ContinuityVerdict.ERROR,
            "commercial_contract",
            "The chapter does not contain any planned character.",
            "Expected: " + ", ".join(plan.characters),
            "Use the approved chapter plan and canonical character names.",
        ))

    if not plan.new_information.strip() or not plan.cliffhanger.strip():
        findings.append(_finding(
            ContinuityVerdict.ERROR,
            "reader_pressure",
            "Chapter plan lacks information gain or an ending question.",
            "new_information/cliffhanger is empty",
            "Revise the chapter plan before generating prose.",
        ))

    lowered = prose.casefold()
    hits = [phrase for phrase in _TEMPLATE_PHRASES if phrase in lowered]
    if hits:
        findings.append(_finding(
            ContinuityVerdict.WARNING,
            "ai_style_risk",
            "The prose contains a strongly templated reveal phrase.",
            ", ".join(hits),
            "Prefer concrete action, subtext, or viewpoint-limited discovery.",
        ))

    if profile.get("anti_ai_rules") and _repeated_sentence_openings(prose):
        findings.append(_finding(
            ContinuityVerdict.WARNING,
            "ai_style_risk",
            "Several consecutive sentences use the same opening pattern.",
            "Repeated sentence openings detected",
            "Vary syntax and paragraph rhythm where it serves the character's voice.",
        ))

    findings.extend(_genre_alignment_findings(prose, contract))

    hook = plan.cliffhanger.strip().casefold()
    recent = [item.content.casefold() for item in context.memories]
    if len(hook) >= 18 and any(hook in item for item in recent):
        findings.append(_finding(
            ContinuityVerdict.WARNING,
            "hook_repetition",
            "The planned ending hook repeats a recent remembered hook or beat.",
            plan.cliffhanger,
            "Change the hook type or add a materially different escalation.",
        ))
    return findings


def _genre_alignment_findings(prose: str, contract: dict) -> list[ContinuityFinding]:
    if contract.get("primary_genre") != "billionaire_romance":
        return []
    lowered = prose.casefold()
    title_signals = [str(item).casefold() for item in contract.get("title_signals", []) if str(item).strip()]
    drift_markers = ("工位", "加班", "办公室", "会议室", "同事", "打卡")
    signal_hits = [item for item in title_signals if item in lowered]
    drift_hits = [item for item in drift_markers if item in prose]
    if drift_hits and not signal_hits:
        return [_finding(
            ContinuityVerdict.ERROR,
            "genre_alignment",
            "正文出现职场场景，但没有兑现豪门总裁类型信号。",
            f"职场词：{', '.join(drift_hits)}；类型词：未发现",
            "让场景直接推动总裁/继承人、豪门权力、身份秘密或核心关系冲突；否则重写本章冲突。",
        )]
    return []


def _repeated_sentence_openings(prose: str) -> bool:
    sentences = [item.strip() for item in re.split(r"[.!?。！？]+", prose) if item.strip()]
    if len(sentences) < 5:
        return False
    openings = [re.sub(r"[^\w']", "", item.split()[0]).casefold() for item in sentences[-8:] if item.split()]
    return len(openings) >= 5 and len(set(openings)) <= max(2, len(openings) // 3)


def _finding(
    severity: ContinuityVerdict,
    category: str,
    problem: str,
    evidence: str,
    recommendation: str,
) -> ContinuityFinding:
    return ContinuityFinding(
        severity=severity,
        category=category,
        problem=problem,
        evidence=evidence,
        recommendation=recommendation,
    )
