from novel_engine.creative.contract import compile_creative_contract
from novel_engine.memory.handoff import build_chapter_handoff
from novel_engine.style.commercial import _genre_alignment_findings


def test_billionaire_contract_contains_reader_facing_signals() -> None:
    contract = compile_creative_contract(
        genre="billionaire_romance",
        audience="女频",
        premise="普通职员卷入豪门股权争夺并接近神秘总裁",
        language="zh-CN",
    )
    assert contract["genre_label"] == "豪门总裁"
    assert "总裁" in contract["title_signals"]
    assert "普通职场日常" in contract["forbidden_drift"]


def test_billionaire_workplace_drift_is_blocked() -> None:
    contract = compile_creative_contract(genre="billionaire_romance", language="zh-CN")
    findings = _genre_alignment_findings("她加班后发现自己的工位被换到了会议室。", contract)
    assert findings
    assert findings[0].category == "genre_alignment"


def test_chapter_handoff_keeps_next_scene_requirements_and_evidence() -> None:
    class Handoff:
        scene_number = 2
        next_scene_requirements = ["处理董事会追责"]
        open_questions = ["谁调包了文件？"]
        unknown_to = {"林妍": ["沈砚的真实身份"]}
        what_happened = "沈砚替林妍承担责任"
        new_information = ["文件涉及继承权"]
        character_changes = ["林妍开始怀疑沈砚"]
        source_excerpt = "沈砚当众签下责任确认书。"

    class Summary:
        scene_handoffs = [Handoff()]
        unresolved_hooks = ["董事会将于明日追责"]
        character_changes = ["林妍开始怀疑沈砚"]

    handoff = build_chapter_handoff(chapter_number=12, summary=Summary())
    assert "处理董事会追责" in handoff.required_inheritance
    assert handoff.evidence[0].chapter_number == 12
    assert handoff.evidence[0].source_excerpt
