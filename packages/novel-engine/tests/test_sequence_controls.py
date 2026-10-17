from types import SimpleNamespace

from novel_engine.style.sequence_controls import (
    ExpressionHistory,
    RevealLedger,
    assess_expression_sequence,
    assess_reveal_plan,
    fingerprint_chapter,
    record_expression,
    record_reveals,
)


def _plan(**updates):
    values = {
        "location": "灰堤",
        "conflict": "裂口正在扩大",
        "cliffhanger": "危险升级",
        "new_information": "发现裂口下有刻纹",
        "reveal": "灰隼曾经来过",
    }
    values.update(updates)
    return SimpleNamespace(**values)


def test_expression_history_flags_repeated_ending_and_imagery():
    history = ExpressionHistory()
    for chapter in (10, 11, 12):
        record_expression(
            history,
            fingerprint_chapter(
                chapter_number=chapter,
                prose="蓝光亮起。心跳从泥下传来。凯尔继续向前。",
                plan=_plan(),
                scenes=[],
                watchlist=["蓝光", "心跳"],
            ),
        )
    current = fingerprint_chapter(
        chapter_number=13,
        prose="蓝光亮起。心跳从泥下传来。凯尔继续向前。",
        plan=_plan(),
        scenes=[],
        watchlist=["蓝光", "心跳"],
    )
    warnings = assess_expression_sequence(current, history)
    assert {item.category for item in warnings} >= {"repeated_ending", "repeated_imagery"}


def test_reveal_ledger_flags_over_budget_and_repeated_information():
    ledger = RevealLedger()
    record_reveals(ledger, chapter_number=12, items=["裂口下有刻纹"])
    plan = _plan(
        new_information="裂口下有刻纹；灰隼曾经来过；铜尺可以开门；封印已经松动",
        reveal="泥鳅知道一条暗路",
    )
    warnings = assess_reveal_plan(plan=plan, scenes=[], ledger=ledger, chapter_number=13)
    assert {item.category for item in warnings} >= {"reveal_budget", "repeated_reveal"}
