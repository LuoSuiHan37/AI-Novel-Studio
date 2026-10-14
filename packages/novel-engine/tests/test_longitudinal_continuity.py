from types import SimpleNamespace

from novel_engine.models.enums import ChapterStatus, ContinuityVerdict
from novel_engine.style.longitudinal_continuity import scan_longitudinal_continuity


def test_longitudinal_audit_detects_missing_memory() -> None:
    chapters = [SimpleNamespace(chapter_number=1, status=ChapterStatus.APPROVED, content="Opening.")]
    findings = scan_longitudinal_continuity(chapters=chapters, target_chapter_count=2)
    categories = {item.category for item in findings}
    assert "chapter_memory_missing" in categories
    assert "chapter_sequence_gap" in categories


def test_longitudinal_audit_checks_handoff_against_next_chapter() -> None:
    chapters = [
        SimpleNamespace(chapter_number=1, status=ChapterStatus.APPROVED, content="A sealed letter appeared."),
        SimpleNamespace(chapter_number=2, status=ChapterStatus.APPROVED, content="They walked home."),
    ]
    findings = scan_longitudinal_continuity(
        chapters=chapters,
        chapter_memories={
            1: {
                "summary": "A letter appeared.",
                "scene_handoffs": [{"scene_number": 1, "next_scene_requirements": ["open the northern gate"]}],
            }
        },
    )
    assert any(item.category == "handoff_not_observed_next_chapter" for item in findings)
    assert not any(item.severity is ContinuityVerdict.ERROR for item in findings)
