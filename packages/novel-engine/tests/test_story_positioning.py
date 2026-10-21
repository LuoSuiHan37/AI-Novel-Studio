from novel_engine.services.story_positioning import (
    ChapterFocus,
    StoryFocus,
    validate_chapter_focus,
    validate_story_focus,
)


def test_story_focus_limits_secondary_threads():
    focus = StoryFocus(
        core_promise="婚约迫使她查父亲死因",
        reader_question="丈夫是否与事故有关？",
        protagonist_goal="救妹妹并查明真相",
        central_opposition="掌控医疗证据的豪门集团",
        primary_thread="婚约调查父亲死亡",
        secondary_threads=["妹妹治疗", "董事会", "母亲失踪"],
    )
    assert "故事定位的次要支线不能超过两条" in validate_story_focus(focus)


def test_chapter_focus_rejects_main_thread_drift():
    story = StoryFocus(
        core_promise="婚约迫使她查父亲死因",
        reader_question="丈夫是否与事故有关？",
        protagonist_goal="救妹妹并查明真相",
        central_opposition="掌控医疗证据的豪门集团",
        primary_thread="婚约调查父亲死亡",
    )
    chapter = ChapterFocus(
        primary_thread="纯董事会争权",
        question_progress="周氏提出收购",
        answered_or_advanced_question="发现周氏掌握一份旧账",
    )
    assert "本章主线与全书冻结主线不一致" in validate_chapter_focus(
        chapter, story_focus=story
    )
