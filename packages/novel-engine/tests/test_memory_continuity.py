from novel_engine.agents.contracts import SceneHandoff
from novel_engine.models.enums import ContinuityVerdict
from novel_engine.style.memory_continuity import scan_scene_handoffs


def test_scene_handoff_accepts_supported_transition() -> None:
    handoff = SceneHandoff(
        scene_number=1,
        what_happened="Mara found the sealed letter.",
        new_information=["The letter names the northern gate."],
        who_knows={"Mara": ["The letter names the northern gate."]},
        unknown_to={"Ilan": ["The letter names the northern gate."]},
        source_excerpt="Mara found the sealed letter.",
    )
    findings = scan_scene_handoffs(
        prose="Mara found the sealed letter and hid it beneath the table.",
        handoffs=[handoff],
        planned_scene_numbers={1},
        allowed_characters={"Mara", "Ilan"},
    )
    assert not [item for item in findings if item.severity is ContinuityVerdict.ERROR]


def test_scene_handoff_reports_knowledge_contradiction() -> None:
    handoff = SceneHandoff(
        scene_number=1,
        what_happened="The truth was revealed.",
        who_knows={"Mara": ["the truth"]},
        unknown_to={"Mara": ["the truth"]},
    )
    findings = scan_scene_handoffs(prose="The truth was revealed.", handoffs=[handoff])
    assert any(item.category == "scene_handoff_knowledge_contradiction" for item in findings)


def test_scene_handoff_warns_when_evidence_is_not_in_prose() -> None:
    handoff = SceneHandoff(
        scene_number=1,
        what_happened="A door opened.",
        source_excerpt="The dragon crossed the frozen sea.",
    )
    findings = scan_scene_handoffs(prose="A door opened quietly.", handoffs=[handoff])
    assert any(item.category == "scene_handoff_evidence_missing" for item in findings)


def test_scene_handoff_detects_missing_scene_and_location_drift() -> None:
    handoff = SceneHandoff(
        scene_number=1,
        location="harbor",
        what_happened="The meeting ended.",
    )
    findings = scan_scene_handoffs(
        prose="The meeting ended.",
        handoffs=[handoff],
        planned_scene_numbers={1, 2},
        planned_scene_locations={1: "castle", 2: "harbor"},
    )
    categories = {item.category for item in findings}
    assert "scene_handoff_missing_scene" in categories
    assert "scene_handoff_location_mismatch" in categories
