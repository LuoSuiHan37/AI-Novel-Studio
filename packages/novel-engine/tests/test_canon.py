from novel_engine.agents.contracts import WriterContext
from novel_engine.style.canon import scan_context_alignment


def _context() -> WriterContext:
    return WriterContext.model_construct(
        characters=[
            type("Character", (), {"name": "Jax", "aliases": []})(),
            type("Character", (), {"name": "Mira", "aliases": []})(),
        ],
        chapter_plan=type(
            "Plan", (), {"characters": ["Jax", "Mira"]}
        )(),
        previous_chapter_summary="",
    )


def test_rejects_chapter_from_another_story():
    prose = (
        "Aria stood before Kael in the Moonridge Pack Hall. "
        "The Alpha rejected her as his mate, and the Luna ceremony ended."
    )
    findings = scan_context_alignment(prose=prose, context=_context())
    assert any(item.category == "story_context_mismatch" for item in findings)


def test_accepts_chapter_using_planned_character():
    findings = scan_context_alignment(
        prose="Jax opened the memory chip while Mira watched the door.",
        context=_context(),
    )
    assert not any(item.severity.value == "ERROR" for item in findings)
