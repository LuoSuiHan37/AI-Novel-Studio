from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.memory import StoryMemory
from novel_engine.services.engine import NovelEngine


def _safe_segment(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" .")
    return value[:80] or "untitled"


def _json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


async def save_project_snapshot(engine: NovelEngine, project_id: UUID) -> Path:
    """Mirror one complete book to the configured local save directory."""
    project = await engine.get_project(project_id)
    story = await engine.story_bibles.get(project_id)
    world = await engine.world_bibles.get(project_id)
    characters = await engine.characters.list(project_id)
    plots = await engine.master_plots.list(project_id)
    arcs = await engine.story_arcs.list(project_id)
    chapters = await engine.chapters.list(project_id)

    root = Path(get_settings().save_root)
    book_dir = root / f"{_safe_segment(project.title)}-{str(project.id)[:8]}"
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    chapter_records: list[dict[str, Any]] = []
    for chapter in sorted(chapters, key=lambda item: item.chapter_number):
        plan = await engine.uow.chapter_plans.latest_for_chapter(chapter.id)
        scenes = await engine.scene_plans.list(plan.id) if plan else []
        chapter_records.append(
            {
                "chapter": _json(chapter),
                "plan": _json(plan) if plan else None,
                "scenes": [_json(item) for item in scenes],
            }
        )
        title = _safe_segment(chapter.title or f"Chapter {chapter.chapter_number}")
        chapter_path = chapters_dir / f"{chapter.chapter_number:03d}-{title}.md"
        chapter_path.write_text(
            "# " + (chapter.title or f"Chapter {chapter.chapter_number}") + "\n\n" + chapter.content,
            encoding="utf-8",
        )

    memories: list[dict[str, Any]] = []
    session = getattr(engine.uow, "session", None)
    if isinstance(session, AsyncSession):
        rows = (
            await session.scalars(
                select(StoryMemory)
                .where(StoryMemory.project_id == project_id)
                .order_by(StoryMemory.chapter_number, StoryMemory.created_at)
            )
        ).all()
        memories = [
            {
                "id": str(row.id),
                "layer": row.layer,
                "epistemic_status": row.epistemic_status,
                "memory_type": row.memory_type,
                "importance": row.importance,
                "content": row.content,
                "chapter_number": row.chapter_number,
                "location": row.location,
                "tags": list(row.tags or []),
                "extra_metadata": row.extra_metadata or {},
            }
            for row in rows
        ]

    payload = {
        "format_version": 1,
        "project": _json(project),
        "story_bible": _json(story) if story else None,
        "world_bible": _json(world) if world else None,
        "characters": [_json(item) for item in characters],
        "master_plots": [_json(item) for item in plots],
        "story_arcs": [_json(item) for item in arcs],
        "chapters": chapter_records,
        "memories": memories,
    }
    (book_dir / "book.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (book_dir / "README.md").write_text(
        f"# {project.title}\n\n本目录由 AI 小说工作室自动保存。\n\n"
        f"- 章节数：{len(chapters)}\n"
        f"- 最后同步：{project.updated_at.isoformat()}\n",
        encoding="utf-8",
    )
    return book_dir
