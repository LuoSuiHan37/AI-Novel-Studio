from app.services.creative_quality import rank_creative_candidates


def test_rank_creative_candidates_filters_duplicates_and_used_titles() -> None:
    ranked = rank_creative_candidates(
        ["她回来时，仇人正在婚礼上", "她回来时，仇人正在婚礼上", "旧书名", "Chapter 1"],
        existing=["旧书名"],
    )

    assert [item["text"] for item in ranked] == ["她回来时，仇人正在婚礼上"]
    assert ranked[0]["score"] >= 70


def test_rank_creative_candidates_prefers_readable_titles() -> None:
    ranked = rank_creative_candidates(
        ["一个非常非常非常非常非常非常长的标题标题标题标题标题", "那张遗书不是父亲写的"]
    )

    assert ranked[0]["text"] == "那张遗书不是父亲写的"
    assert "长度适合移动端展示" in ranked[0]["reasons"]
