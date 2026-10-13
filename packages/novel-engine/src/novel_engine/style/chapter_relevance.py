from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field


class ChapterRelevanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "passed"
    blocked: bool = False
    score: int = 0
    character_match: bool = False
    location_match: bool = False
    plan_term_overlap: float = 0.0
    scene_coverage: float = 1.0
    missing_scene_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    plan_satisfaction: float = 1.0
    reason: str | None = None


def _units(text: str) -> set[str]:
    lowered = text.casefold()
    words = set(re.findall(r"[a-z0-9][a-z0-9'_-]{1,}|[\u3400-\u9fff]{2,}", lowered))
    return {word for word in words if len(word) > 1}


def scan_chapter_relevance(*, content: str, plan: object, scenes: list[object] | None = None) -> ChapterRelevanceReport:
    """Cheap deterministic guard against a chapter drifting off its plan.

    This is deliberately conservative: it blocks only when the chapter has no
    detectable connection to the planned people, place, or story terms. A
    model-based literary audit remains responsible for nuanced relevance.
    """

    text = content.casefold()
    characters = [str(item).strip() for item in (getattr(plan, "characters", []) or []) if str(item).strip()]
    character_match = any(name.casefold() in text for name in characters)
    location = str(getattr(plan, "location", "") or "").strip()
    location_match = bool(location and location.casefold() in text)
    plan_text = " ".join(
        str(getattr(plan, field, "") or "")
        for field in ("chapter_goal", "conflict", "new_information", "reveal", "cliffhanger")
    )
    terms = _units(plan_text)
    overlap = len(terms & _units(content)) / len(terms) if terms else 1.0
    score = (40 if character_match else 0) + (20 if location_match else 0) + round(min(40, overlap * 40))
    missing: list[str] = []
    if characters and not character_match:
        missing.append("planned characters are absent")
    if location and not location_match:
        missing.append("planned location is absent")
    if terms and overlap < 0.20:
        missing.append("planned conflict or information is not reflected")
    scene_requirements: list[str] = []
    covered_scenes = 0
    for scene in scenes or []:
        scene_text = " ".join(
            str(getattr(scene, field, "") or "")
            for field in ("location", "goal", "conflict", "turning_point", "information_revealed", "ending")
        )
        scene_terms = _units(scene_text)
        scene_overlap = len(scene_terms & _units(content)) / len(scene_terms) if scene_terms else 1.0
        scene_characters = [str(item).strip() for item in (getattr(scene, "characters", []) or []) if str(item).strip()]
        scene_location = str(getattr(scene, "location", "") or "").strip()
        scene_character_match = any(name.casefold() in text for name in scene_characters)
        scene_location_match = bool(scene_location and scene_location.casefold() in text)
        # A scene is covered only when the prose contains its people/place and
        # a meaningful part of its planned action or information.  Merely
        # mentioning a character is not evidence that the planned scene happened.
        scene_connected = (
            (scene_character_match or scene_location_match)
            and scene_overlap >= 0.20
        )
        if scene_connected:
            covered_scenes += 1
        else:
            scene_requirements.append(f"scene {getattr(scene, 'scene_number', '?')} requirements are not reflected")
    scene_coverage = covered_scenes / len(scenes) if scenes else 1.0
    missing.extend(scene_requirements)
    plan_satisfaction = min(
        1.0,
        (int(character_match) + int(location_match) + min(1.0, overlap * 2.0)) / 3.0,
    )
    # The deterministic layer blocks only clearly unrelated prose.  Missing
    # scene details remain an explicit finding for the independent automated
    # reviewer; exact lexical matching alone must not reject valid paraphrase.
    blocked = bool(content.strip()) and bool(
        not character_match and not location_match and overlap < 0.20
    )
    if scenes and scene_coverage == 0 and not character_match and not location_match:
        blocked = True
    return ChapterRelevanceReport(
        status="blocked" if blocked else "passed",
        blocked=blocked,
        score=score,
        character_match=character_match,
        location_match=location_match,
        plan_term_overlap=round(overlap, 4),
        scene_coverage=round(scene_coverage, 4),
        plan_satisfaction=round(plan_satisfaction, 4),
        missing_scene_requirements=scene_requirements,
        missing_requirements=missing,
        reason="chapter has no detectable connection to its approved plan" if blocked else None,
    )
