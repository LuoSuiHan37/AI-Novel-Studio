from types import SimpleNamespace
from uuid import uuid4

from novel_engine.models.enums import ContinuityVerdict, ForeshadowStatus, HookStatus
from novel_engine.style.plot_thread_lifecycle import scan_plot_thread_lifecycle


def test_plot_thread_lifecycle_detects_invalid_resolution() -> None:
    setup_id = uuid4()
    resolved_id = uuid4()
    hook = SimpleNamespace(
        status=HookStatus.RESOLVED,
        setup_chapter_id=setup_id,
        resolved_chapter_id=None,
        description="Who opened the gate?",
    )
    foreshadow = SimpleNamespace(
        status=ForeshadowStatus.PAID_OFF,
        setup_chapter_id=setup_id,
        expected_payoff_chapter_id=resolved_id,
        actual_payoff_chapter_id=None,
        description="The silver mark",
    )
    findings = scan_plot_thread_lifecycle(
        hooks=[hook],
        foreshadowings=[foreshadow],
        chapter_numbers={setup_id: 4, resolved_id: 3},
        latest_approved_chapter=5,
    )
    categories = {item.category for item in findings}
    assert "hook_resolution_missing" in categories
    assert "foreshadow_payoff_missing" in categories
    assert "foreshadow_payoff_order" in categories
    assert any(item.severity is ContinuityVerdict.ERROR for item in findings)


def test_plot_thread_lifecycle_reports_overdue_foreshadowing() -> None:
    setup_id = uuid4()
    expected_id = uuid4()
    item = SimpleNamespace(
        status=ForeshadowStatus.PLANTED,
        setup_chapter_id=setup_id,
        expected_payoff_chapter_id=expected_id,
        actual_payoff_chapter_id=None,
        description="The hidden key",
    )
    findings = scan_plot_thread_lifecycle(
        hooks=[],
        foreshadowings=[item],
        chapter_numbers={setup_id: 2, expected_id: 5},
        latest_approved_chapter=7,
    )
    assert any(item.category == "foreshadow_overdue" for item in findings)
