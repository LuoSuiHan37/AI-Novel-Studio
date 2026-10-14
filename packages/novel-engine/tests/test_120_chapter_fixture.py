"""Isolated structural stress fixture.

This test never writes to the application database and does not represent real
novel prose. It verifies that the deterministic audit components can process a
120-chapter memory shape without confusing test data with a user's project.
"""

from types import SimpleNamespace

from novel_engine.models.enums import ChapterStatus
from novel_engine.style.longitudinal_continuity import scan_longitudinal_continuity
from novel_engine.style.plot_thread_lifecycle import scan_plot_thread_lifecycle
from novel_engine.style.story_state_continuity import scan_story_state_continuity


def test_isolated_120_chapter_structural_fixture() -> None:
    chapters = [
        SimpleNamespace(
            chapter_number=number,
            status=ChapterStatus.APPROVED,
            content=f"Synthetic fixture chapter {number}.",
            id=f"chapter-{number}",
        )
        for number in range(1, 121)
    ]
    memories = {
        number: {
            "summary": f"Synthetic fixture summary {number}.",
            "scene_handoffs": [
                {
                    "scene_number": 1,
                    "next_scene_requirements": [],
                }
            ],
        }
        for number in range(1, 121)
    }
    plans = {
        number: SimpleNamespace(location=f"fixture-location-{number}", characters=["FixtureHero"])
        for number in range(1, 121)
    }
    timeline = [SimpleNamespace(sequence=number) for number in range(1, 121)]
    findings = [
        *scan_longitudinal_continuity(
            chapters=chapters,
            chapter_memories=memories,
            target_chapter_count=120,
        ),
        *scan_story_state_continuity(
            chapters=chapters,
            plans=plans,
            timeline_events=timeline,
            memory_rows=[],
        ),
        *scan_plot_thread_lifecycle(
            hooks=[],
            foreshadowings=[],
            chapter_numbers={chapter.id: chapter.chapter_number for chapter in chapters},
            latest_approved_chapter=120,
        ),
    ]
    assert not findings
