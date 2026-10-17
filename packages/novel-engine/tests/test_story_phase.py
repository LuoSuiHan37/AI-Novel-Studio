from novel_engine.style.story_phase import classify_story_phase


def test_story_phase_is_deterministic_and_progressive():
    assert classify_story_phase(chapter_number=1, target_chapters=100).key == "opening"
    assert classify_story_phase(chapter_number=20, target_chapters=100).key == "investigation"
    assert classify_story_phase(chapter_number=55, target_chapters=100).key == "escalation"
    assert classify_story_phase(chapter_number=95, target_chapters=100).key == "crisis"


def test_story_phase_has_a_fallback_when_total_length_is_unknown():
    assert classify_story_phase(chapter_number=15).key == "investigation"
