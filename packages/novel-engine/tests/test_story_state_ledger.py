from uuid import uuid4

from novel_engine.models.enums import ContinuityVerdict
from novel_engine.models.story_state import (
    EntityStateChange,
    ResourceStateChange,
    StoryEntityState,
    StoryResourceState,
    StoryState,
    StoryStateDelta,
    apply_state_delta,
)


def test_active_entity_missing_from_observation_is_flagged_without_being_deleted() -> None:
    state = StoryState(
        project_id=uuid4(),
        entities=[StoryEntityState(canonical_name="Pup A", last_seen_chapter=1)],
    )
    updated, findings = apply_state_delta(
        state,
        StoryStateDelta(observed_entities=[]),
        chapter_number=2,
    )
    assert updated.entity("Pup A") is not None
    assert not findings

    updated, findings = apply_state_delta(
        state,
        StoryStateDelta(observed_entities=["Kael"]),
        chapter_number=2,
    )
    assert updated.entity("Pup A").status == "active"
    assert any(item.category == "active_entity_not_observed" for item in findings)
    assert any(item.severity is ContinuityVerdict.WARNING for item in findings)


def test_resource_cannot_be_consumed_below_zero() -> None:
    state = StoryState(
        project_id=uuid4(),
        resources=[StoryResourceState(name="salt crystal", quantity=2)],
    )
    _, findings = apply_state_delta(
        state,
        StoryStateDelta(resources=[ResourceStateChange(
            name="salt crystal",
            action="consume",
            quantity=3,
            evidence="The prose claims three crystals were consumed.",
        )]),
        chapter_number=2,
    )
    assert any(item.category == "resource_negative" for item in findings)
    assert any(item.severity is ContinuityVerdict.ERROR for item in findings)


def test_terminal_entity_cannot_reappear() -> None:
    state = StoryState(
        project_id=uuid4(),
        entities=[StoryEntityState(canonical_name="Mud Beast", status="dead")],
    )
    _, findings = apply_state_delta(
        state,
        StoryStateDelta(entities=[EntityStateChange(
            canonical_name="Mud Beast",
            action="update",
            status="active",
            evidence="The beast attacks again.",
        )]),
        chapter_number=3,
    )
    assert any(item.category == "terminal_entity_reappeared" for item in findings)
