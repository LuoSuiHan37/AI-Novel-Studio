from __future__ import annotations

from typing import Any

from novel_engine.memory.models import ChapterHandoff, HandoffEvidence


def build_chapter_handoff(*, chapter_number: int, summary: Any) -> ChapterHandoff:
    scene_handoffs = list(getattr(summary, "scene_handoffs", []) or [])
    immediate: list[str] = []
    questions: list[str] = list(getattr(summary, "unresolved_hooks", []) or [])
    required: list[str] = []
    forbidden: list[str] = []
    evidence: list[HandoffEvidence] = []
    confirmed: list[str] = []
    for item in scene_handoffs:
        immediate.extend(item.next_scene_requirements)
        questions.extend(item.open_questions)
        required.extend(item.next_scene_requirements)
        for character, facts in item.unknown_to.items():
            forbidden.extend(f"{character}不得提前知道：{fact}" for fact in facts)
        for fact in (item.what_happened, *item.new_information, *item.character_changes):
            if fact.strip():
                confirmed.append(fact.strip())
                evidence.append(HandoffEvidence(
                    chapter_number=chapter_number,
                    scene_number=item.scene_number,
                    fact=fact.strip(),
                    source_excerpt=item.source_excerpt.strip(),
                ))
    return ChapterHandoff(
        chapter_number=chapter_number,
        immediate_consequences=list(dict.fromkeys(item for item in immediate if item.strip())),
        character_changes=list(dict.fromkeys(getattr(summary, "character_changes", []) or [])),
        confirmed_facts=list(dict.fromkeys(confirmed)),
        unresolved_questions=list(dict.fromkeys(item for item in questions if item.strip())),
        open_hooks=list(dict.fromkeys(getattr(summary, "unresolved_hooks", []) or [])),
        required_inheritance=list(dict.fromkeys(item for item in required if item.strip())),
        forbidden_reveals=list(dict.fromkeys(item for item in forbidden if item.strip())),
        evidence=evidence,
    )
