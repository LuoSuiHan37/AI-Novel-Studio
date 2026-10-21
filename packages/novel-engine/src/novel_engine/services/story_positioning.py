from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StoryFocus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_promise: str = ""
    core_promise: str
    reader_question: str
    protagonist_goal: str
    central_opposition: str
    primary_thread: str
    secondary_threads: list[str] = Field(default_factory=list)
    forbidden_drifts: list[str] = Field(default_factory=list)


class ChapterFocus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_thread: str
    question_progress: str
    answered_or_advanced_question: str
    new_major_mysteries: list[str] = Field(default_factory=list, max_length=1)
    resolved_or_narrowed_mysteries: list[str] = Field(default_factory=list)


def validate_story_focus(focus: StoryFocus) -> list[str]:
    missing = [
        name for name in (
            "core_promise", "reader_question", "protagonist_goal",
            "central_opposition", "primary_thread",
        ) if not getattr(focus, name).strip()
    ]
    errors = [f"故事定位缺少字段：{', '.join(missing)}"] if missing else []
    if len(focus.secondary_threads) > 2:
        errors.append("故事定位的次要支线不能超过两条")
    if focus.primary_thread.strip() in {item.strip() for item in focus.secondary_threads}:
        errors.append("主线不能同时列为次要支线")
    return errors


def validate_chapter_focus(focus: ChapterFocus, *, story_focus: StoryFocus) -> list[str]:
    errors: list[str] = []
    if focus.primary_thread.strip() != story_focus.primary_thread.strip():
        errors.append("本章主线与全书冻结主线不一致")
    if not focus.question_progress.strip():
        errors.append("本章没有说明核心问题如何推进")
    if not focus.answered_or_advanced_question.strip():
        errors.append("本章没有回答或推进前文问题")
    return errors
