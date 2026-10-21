from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from novel_engine.models.enums import ApprovalStatus, ChapterStatus
from novel_engine.ports.repositories import NovelUnitOfWork
from novel_engine.style.chapter_repetition import scan_book_repetition
from novel_engine.services.story_positioning import (
    ChapterFocus,
    StoryFocus,
    validate_chapter_focus,
    validate_story_focus,
)


@dataclass(frozen=True)
class AuditFinding:
    code: str
    message: str
    blocking: bool = True


@dataclass(frozen=True)
class NovelAuditReport:
    findings: tuple[AuditFinding, ...]

    @property
    def passed(self) -> bool:
        return not any(item.blocking for item in self.findings)

    @property
    def blocking_messages(self) -> tuple[str, ...]:
        return tuple(item.message for item in self.findings if item.blocking)


async def audit_novel_for_publish(
    uow: NovelUnitOfWork,
    project: Any,
) -> NovelAuditReport:
    """Run deterministic whole-book checks immediately before publication.

    This is intentionally conservative: it does not claim that prose is good,
    only that known structural failure modes are not allowed through the final
    gate. LLM review remains useful, but cannot replace these invariants.
    """

    findings: list[AuditFinding] = []
    metadata = project.extra_metadata or {}
    raw_focus = metadata.get("story_focus")
    focus_required = bool(metadata.get("story_focus_required") or raw_focus)
    story_focus = None
    if focus_required and not isinstance(raw_focus, dict):
        findings.append(AuditFinding("story_focus_missing", "没有冻结全书核心卖点和主线"))
    elif isinstance(raw_focus, dict):
        try:
            story_focus = StoryFocus.model_validate(raw_focus)
            findings.extend(AuditFinding("story_focus_invalid", item) for item in validate_story_focus(story_focus))
        except Exception as exc:
            findings.append(AuditFinding("story_focus_invalid", f"故事定位格式无效：{exc}"))
    chapters = await uow.chapters.list_by_project(project.id)
    numbers = [int(item.chapter_number) for item in chapters]
    duplicates = sorted(number for number, count in Counter(numbers).items() if count > 1)
    if duplicates:
        findings.append(
            AuditFinding("duplicate_chapter_number", f"存在重复章节号：{', '.join(map(str, duplicates))}")
        )

    title_groups: dict[str, list[int]] = {}
    for chapter in chapters:
        key = _normalize_title(chapter.title)
        if key:
            title_groups.setdefault(key, []).append(int(chapter.chapter_number))
    for title, title_numbers in title_groups.items():
        if len(title_numbers) > 1:
            findings.append(
                AuditFinding(
                    "duplicate_chapter_title",
                    f"章节标题重复（{title}）：章节 {', '.join(map(str, sorted(title_numbers)))}",
                )
            )

    target = project.chapter_count_target
    unique_numbers = set(numbers)
    if target:
        missing = [number for number in range(1, target + 1) if number not in unique_numbers]
        if missing:
            findings.append(AuditFinding("missing_chapter", f"缺少章节：{_preview(missing)}"))
        overflow = sorted(number for number in unique_numbers if number > target)
        if overflow:
            findings.append(AuditFinding("chapter_overflow", f"章节超过目标总数：{_preview(overflow)}"))

    for chapter in chapters:
        number = int(chapter.chapter_number)
        if not str(chapter.content or "").strip():
            findings.append(AuditFinding("empty_chapter", f"第 {number} 章没有正文"))
        if chapter.status not in {ChapterStatus.APPROVED, ChapterStatus.PUBLISHED}:
            findings.append(AuditFinding("chapter_not_approved", f"第 {number} 章尚未通过审核"))
        plan = await uow.chapter_plans.latest_for_chapter(chapter.id)
        if plan is None or plan.status is not ApprovalStatus.APPROVED:
            findings.append(AuditFinding("chapter_plan_not_approved", f"第 {number} 章没有已批准的章节计划"))
            continue
        scenes = await uow.scene_plans.list_by_plan(plan.id)
        if not scenes:
            findings.append(AuditFinding("missing_scene_plan", f"第 {number} 章没有场景计划"))
            continue
        for scene in scenes:
            missing_scene_fields = [
                name for name in ("protagonist_want", "active_pressure", "choice_and_cost", "irreversible_change")
                if not str(getattr(scene, name, "") or "").strip()
            ]
            if missing_scene_fields:
                findings.append(
                    AuditFinding(
                        "scene_agency_contract_missing",
                        f"第 {number} 章场景 {scene.scene_number} 缺少主动性约束：{', '.join(missing_scene_fields)}",
                    )
                )
        if story_focus is not None:
            raw_chapter_focus = (chapter.extra_metadata or {}).get("story_focus")
            if not isinstance(raw_chapter_focus, dict):
                findings.append(AuditFinding("chapter_focus_missing", f"第 {number} 章没有主线推进记录"))
            else:
                try:
                    chapter_focus = ChapterFocus.model_validate(raw_chapter_focus)
                    findings.extend(
                        AuditFinding("chapter_focus_invalid", f"第 {number} 章：{item}")
                        for item in validate_chapter_focus(chapter_focus, story_focus=story_focus)
                    )
                except Exception as exc:
                    findings.append(AuditFinding("chapter_focus_invalid", f"第 {number} 章主线记录格式无效：{exc}"))

    findings.extend(
        AuditFinding(
            "book_repetition",
            f"第 {item['chapter_number']} 章与第 {item['matched_chapter_number']} 章重复：{item['reason']}",
        )
        for item in scan_book_repetition(chapters)
    )
    return NovelAuditReport(findings=tuple(findings))


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _preview(values: list[int]) -> str:
    shown = ", ".join(map(str, values[:12]))
    return shown + ("..." if len(values) > 12 else "")
