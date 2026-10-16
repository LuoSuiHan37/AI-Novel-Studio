from app.services.work_tags import WORK_TAG_CATALOG, default_work_tags, validate_work_tags


def test_all_default_work_tags_are_supported() -> None:
    for genre in ("billionaire_romance", "werewolf_romance", "progression_fantasy"):
        defaults = default_work_tags(genre)
        assert validate_work_tags(defaults, allow_empty=False) == defaults


def test_new_billionaire_plot_tags_are_supported() -> None:
    assert "豪门恩怨" in WORK_TAG_CATALOG["plot"]
    assert "身份反转" in WORK_TAG_CATALOG["plot"]


def test_unknown_tags_are_dropped_instead_of_blocking_creation() -> None:
    value = {
        "style": ["甜宠"],
        "role": ["豪门总裁"],
        "plot": ["旧版本标签", "豪门恩怨"],
        "background": ["都市"],
        "old_category": ["旧版本标签"],
    }

    assert validate_work_tags(value, allow_empty=False) == {
        "style": ["甜宠"],
        "role": ["豪门总裁"],
        "plot": ["豪门恩怨"],
        "background": ["都市"],
    }


def test_unknown_only_required_category_is_omitted_without_blocking() -> None:
    value = {
        "style": ["甜宠"],
        "role": ["豪门总裁"],
        "plot": ["旧版本标签"],
        "background": ["都市"],
    }

    assert validate_work_tags(value, allow_empty=False)["plot"] == []
