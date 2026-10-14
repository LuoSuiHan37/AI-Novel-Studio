from types import SimpleNamespace

from novel_engine.models.enums import ChapterStatus, ContinuityVerdict
from novel_engine.style.story_state_continuity import scan_story_state_continuity


def test_story_state_checks_timeline_and_plan_contracts() -> None:
    chapters = [SimpleNamespace(chapter_number=1, status=ChapterStatus.APPROVED)]
    findings = scan_story_state_continuity(
        chapters=chapters,
        plans={1: SimpleNamespace(location="", characters=[])},
        timeline_events=[SimpleNamespace(sequence=1), SimpleNamespace(sequence=1)],
    )
    categories = {item.category for item in findings}
    assert "chapter_location_missing" in categories
    assert "chapter_characters_missing" in categories
    assert "timeline_sequence_duplicate" in categories
    assert any(item.severity is ContinuityVerdict.ERROR for item in findings)


def test_story_state_checks_plot_beat_evidence() -> None:
    chapters = [SimpleNamespace(chapter_number=3, status=ChapterStatus.APPROVED)]
    beat = SimpleNamespace(name="The Gate Opens", description="The northern gate opens", chapter_hint=3)
    memory = SimpleNamespace(
        chapter_number=3,
        content="The characters rested.",
        known_by=[],
        unknown_to=[],
        extra_metadata={"kind": "chapter_memory"},
    )
    findings = scan_story_state_continuity(
        chapters=chapters,
        plans={3: SimpleNamespace(location="gate", characters=["Mara"])},
        plot_beats=[beat],
        memory_rows=[memory],
    )
    assert any(item.category == "plot_beat_evidence_missing" for item in findings)
