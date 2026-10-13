from novel_engine.research.executor import _split_chapters


def test_split_chapters_drops_exact_duplicate_source_blocks() -> None:
    text = "# Chapter 1\nThe same prose.\n\n# Chapter 4\nThe same prose.\n\n# Chapter 2\nNew prose."

    chapters = _split_chapters(text)

    assert [item["chapter_number"] for item in chapters] == [1, 2]
    assert [item["title"] for item in chapters] == ["Chapter 1", "Chapter 2"]
