from novel_engine.creative.profile import compile_creative_profile
from novel_engine.presets.loader import resolve_style_bundle


def test_chinese_projects_infer_fanqie_when_platform_is_unspecified() -> None:
    bundle = resolve_style_bundle(platform_id=None, novel_id="werewolf_romance", language="zh-CN")
    assert bundle.platform.id == "fanqie"
    assert bundle.platform.language == "zh-CN"
    assert "character_choice" in bundle.platform.required_beats
    assert bundle.platform.environment_requirements


def test_creative_profile_has_book_constitution_and_literary_rubric() -> None:
    profile = compile_creative_profile(
        {
            "positioning": "A romance about boundaries and earned trust.",
            "environment_bible": {
                "recurring_locations": ["地下档案室"],
                "environmental_constraints": ["玻璃会议室无法真正私密"],
            },
        }
    )
    assert profile["schema_version"] == "2.0"
    assert profile["reader_promise"]
    assert profile["environment_bible"]["recurring_locations"] == ["地下档案室"]
    assert profile["literary_review_rubric"]
