from types import SimpleNamespace

from novel_engine.style.chapter_relevance import scan_chapter_relevance


def _plan(**overrides):
    values = {
        "characters": ["Aria"],
        "location": "the pack hall",
        "chapter_goal": "Aria confronts the alpha and learns the treaty is broken",
        "conflict": "the alpha refuses to explain the blood oath",
        "new_information": "the treaty is a lie",
        "reveal": "",
        "cliffhanger": "the sealed door opens",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_relevance_accepts_planned_people_place_and_story_terms() -> None:
    report = scan_chapter_relevance(
        content="Aria entered the pack hall. The alpha refused to explain the blood oath, and the treaty was a lie. The sealed door opened.",
        plan=_plan(),
    )

    assert report.blocked is False
    assert report.character_match is True
    assert report.location_match is True


def test_relevance_blocks_unrelated_nonempty_chapter() -> None:
    report = scan_chapter_relevance(
        content="A merchant counted coins beside the river and discussed tomorrow's weather.",
        plan=_plan(),
    )

    assert report.blocked is True
    assert report.status == "blocked"


def test_relevance_reports_uncovered_scene_requirements() -> None:
    report = scan_chapter_relevance(
        content="Aria walked through the pack hall and waited in silence.",
        plan=_plan(),
        scenes=[
            SimpleNamespace(
                scene_number=1,
                location="the pack hall",
                characters=["Aria"],
                goal="Aria confronts the alpha",
                conflict="the alpha refuses to explain the blood oath",
                turning_point="the treaty is a lie",
                information_revealed="the treaty is a lie",
                ending="the sealed door opens",
            )
        ],
    )

    assert report.blocked is False
    assert report.scene_coverage == 1.0
