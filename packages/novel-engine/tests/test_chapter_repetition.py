from types import SimpleNamespace

from novel_engine.style.chapter_repetition import scan_book_repetition, scan_chapter_repetition


def _chapter(number: int, content: str):
    return SimpleNamespace(chapter_number=number, content=content)


def test_exact_duplicate_content_is_blocked_even_when_titles_differ() -> None:
    chapters = [_chapter(1, "第一段内容。\n\n第二段内容。"), _chapter(4, "第一段内容。\n\n第二段内容。")]

    report = scan_chapter_repetition(chapter_number=4, content=chapters[1].content, chapters=chapters)

    assert report.blocked is True
    assert report.matches[0].chapter_number == 1
    assert report.matches[0].exact is True


def test_full_book_scan_returns_each_duplicate_pair_once() -> None:
    chapters = [_chapter(1, "第一段内容。\n\n第二段内容。"), _chapter(2, "新的内容。"), _chapter(4, "第一段内容。\n\n第二段内容。")]

    findings = scan_book_repetition(chapters)

    assert len(findings) == 1
    assert findings[0]["chapter_number"] == 1
    assert findings[0]["matched_chapter_number"] == 4


def test_lightly_rewritten_long_chapters_are_blocked() -> None:
    first = "Aria entered the pack hall and confronted the alpha about the broken treaty. " * 30
    rewritten = "Aria walked into the pack hall and challenged the alpha over the broken treaty. " * 30

    report = scan_chapter_repetition(
        chapter_number=2,
        content=rewritten,
        chapters=[_chapter(1, first)],
    )

    assert report.blocked is True
    assert "改写" in report.matches[0].reason
