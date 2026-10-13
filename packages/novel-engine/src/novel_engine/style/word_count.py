from __future__ import annotations

import re


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def count_text_units(text: str) -> int:
    """Count CJK prose by non-whitespace characters, English prose by words."""
    if _CJK_RE.search(text):
        return sum(not char.isspace() for char in text)
    return len(text.split())
