from types import SimpleNamespace

from novel_engine.models.enums import ContinuityVerdict
from novel_engine.style.quality_gate import evaluate_chapter_quality


def _editor(needs_human_review=False):
    return SimpleNamespace(needs_human_review=needs_human_review)


def _continuity(overall=ContinuityVerdict.PASS):
    return SimpleNamespace(overall=overall)


def test_quality_gate_blocks_structural_sequence_repetition():
    warning = SimpleNamespace(category="repeated_character_behavior")
    result = evaluate_chapter_quality(
        continuity=_continuity(),
        editor=_editor(),
        length_ok=True,
        repetition_check={"blocked": False},
        relevance_check={"blocked": False},
        sequence_review=[warning],
    )
    assert result.passed is False
    assert "repeated_character_behavior" in result.blocking_reasons


def test_quality_gate_requires_independent_review_for_automatic_promotion():
    result = evaluate_chapter_quality(
        continuity=_continuity(),
        editor=_editor(),
        length_ok=True,
        repetition_check={"blocked": False},
        relevance_check={"blocked": False},
        sequence_review=[],
        require_independent_review=True,
        commercial=None,
    )
    assert result.passed is False
    assert "independent_review_missing" in result.blocking_reasons


def test_quality_gate_allows_clean_reviewed_chapter():
    commercial = SimpleNamespace(
        reader_pressure_score=8,
        reader_promise_score=8,
        rhythm_score=7,
        ai_style_risk_score=7,
    )
    result = evaluate_chapter_quality(
        continuity=_continuity(),
        editor=_editor(),
        length_ok=True,
        repetition_check={"blocked": False},
        relevance_check={"blocked": False},
        sequence_review=[],
        commercial=commercial,
        require_independent_review=True,
    )
    assert result.passed is True
