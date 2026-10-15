from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from novel_engine.providers.base import LLMProvider
from novel_engine.providers.types import ChatMessage
from novel_engine.prompts.loader import dump_prompt_value, load_prompt, render_prompt
from novel_engine.research.models import CreativeProfile, InjectionProposal, SourceDistillation, SynthesisResult

MAX_SOURCE_BYTES = 8 * 1024 * 1024
CHAPTER_RE = re.compile(r"(?im)^(?:#{1,6}\s+(.+)|第\s*[0-9零一二三四五六七八九十百]+\s*章[^\n]*|chapter\s+[0-9]+[^\n]*)$")


def _split_chapters(text: str) -> list[dict[str, Any]]:
    matches = list(CHAPTER_RE.finditer(text))
    if not matches:
        chunks = [text[index:index + 12000] for index in range(0, len(text), 12000)]
        return [
            {"chapter_number": index + 1, "title": f"Section {index + 1}", "chars": len(chunk), "text": chunk}
            for index, chunk in enumerate(chunks)
            if chunk.strip()
        ]
    chapters: list[dict[str, Any]] = []
    seen_content_fingerprints: set[str] = set()
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[match.start():end].strip()
        title = (match.group(1) or match.group(0)).strip().lstrip("# ")
        # Some novel pages render the same chapter body under different
        # headings.  Use the body, not the title, as the exact-duplicate key.
        # This catches chapter 4 containing a copy of chapter 1 as well as
        # duplicated mobile/desktop blocks.
        body = re.sub(r"^\s*[^\n]+\n?", "", chunk, count=1)
        content_fingerprint = re.sub(r"\s+", " ", body).strip().casefold()
        if content_fingerprint in seen_content_fingerprints:
            continue
        seen_content_fingerprints.add(content_fingerprint)
        chapters.append({"chapter_number": len(chapters) + 1, "title": title[:160], "chars": len(chunk), "text": chunk})
    return chapters


def _read_source(source: dict[str, Any]) -> dict[str, Any]:
    path_value = source.get("path")
    path: Path | None = None
    if path_value:
        path = Path(path_value).expanduser().resolve()
        configured_root = os.environ.get("NOVEL_RESEARCH_ROOT")
        repo_root = Path(configured_root).expanduser().resolve() if configured_root else Path(__file__).resolve().parents[5]
        if not path.is_relative_to(repo_root):
            raise ValueError(f"参考作品必须位于研究根目录内：{repo_root}")
        if path.suffix.lower() not in {".md", ".markdown", ".txt"}:
            raise ValueError(f"暂只支持 Markdown/TXT：{path.name}")
        if not path.is_file():
            raise FileNotFoundError(f"找不到参考作品文件：{path}")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError(f"参考作品过大，单文件不能超过 {MAX_SOURCE_BYTES // 1024 // 1024}MB")
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        url = str(source.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"参考作品“{source.get('title', '未命名')}”需要有效的本地路径或网页链接")
        try:
            response = httpx.get(url, follow_redirects=True, timeout=30, headers={"User-Agent": "AI-Novel-Studio/1.0"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValueError(f"无法读取参考作品链接：{exc}") from exc
        if len(response.content) > MAX_SOURCE_BYTES:
            raise ValueError(f"参考作品过大，单个链接内容不能超过 {MAX_SOURCE_BYTES // 1024 // 1024}MB")
        text = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", response.text)
        text = re.sub(r"(?s)<[^>]+>", "\n", text)
        text = re.sub(r"\s+", " ", text)
        if len(text.strip()) < 100:
            raise ValueError("链接没有读取到足够的正文内容，请使用番茄小说章节页链接或改用 TXT/Markdown 文件")
    chapters = _split_chapters(text)
    return {
        **source,
        "path": str(path) if path else None,
        "chapter_count": len(chapters),
        "word_count": len(re.findall(r"\w+|[^\s]", text)),
        "status": "ready",
        "chapters": [{key: item[key] for key in ("chapter_number", "title", "chars")} for item in chapters],
        "_chapter_text": chapters,
    }


def _layered_sample(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select representative chapters across a serial novel's lifecycle."""
    if not chapters:
        return []
    count = len(chapters)
    indexes = {0, min(1, count - 1), min(2, count - 1), min(4, count - 1)}
    indexes.update(range(5, min(10, count)))
    indexes.update({count // 3, (count * 2) // 3, max(0, count - 3), count - 1})
    return [chapters[index] for index in sorted(indexes) if 0 <= index < count]


class DistillationExecutor:
    """Runs one observable distillation stage and returns JSON-safe artifacts."""

    async def ingest(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [_read_source(source) for source in sources]

    async def analyze(
        self,
        provider: LLMProvider,
        sources: list[dict[str, Any]],
        on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> list[dict[str, Any]]:
        prompt = load_prompt("research/distill_source.yaml")
        results = []
        for source in sources:
            chapters = source.get("_chapter_text") or []
            selected = _layered_sample(chapters)
            if on_progress:
                await on_progress({
                    "source_id": source.get("id"),
                    "source_title": source.get("title", "未命名作品"),
                    "phase": "sampling",
                    "sampled_chapter_numbers": [item["chapter_number"] for item in selected],
                    "sampled_chapter_titles": [item["title"] for item in selected],
                })
            sample = "\n\n".join(
                f"[Sample chapter {item['chapter_number']}: {item['title']}]\n{item['text'][:2200]}"
                for item in selected
            )[:24000]
            source_meta = {k: v for k, v in source.items() if not k.startswith("_")}
            source_meta["sampled_chapter_numbers"] = [item["chapter_number"] for item in selected]
            rendered = render_prompt(prompt, source=dump_prompt_value(source_meta), sample=sample)
            result, _ = await provider.generate_json(
                [ChatMessage(role="system", content=rendered), ChatMessage(role="user", content="Return the structured distillation now.")],
                SourceDistillation,
                temperature=0.25,
            )
            results.append(result.model_dump())
            if on_progress:
                await on_progress({
                    "source_id": source.get("id"),
                    "source_title": source.get("title", "未命名作品"),
                    "phase": "completed",
                    "sampled_chapter_numbers": [item["chapter_number"] for item in selected],
                    "sampled_chapter_titles": [item["title"] for item in selected],
                })
        return results

    async def synthesize(self, provider: LLMProvider, analyses: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = load_prompt("research/synthesize.yaml")
        rendered = render_prompt(prompt, analyses=dump_prompt_value(analyses))
        result, _ = await provider.generate_json(
            [ChatMessage(role="system", content=rendered), ChatMessage(role="user", content="Return the cross-book synthesis now.")],
            SynthesisResult,
            temperature=0.25,
        )
        return result.model_dump()

    async def profile(self, provider: LLMProvider, synthesis: dict[str, Any]) -> dict[str, Any]:
        prompt = load_prompt("research/profile.yaml")
        rendered = render_prompt(prompt, synthesis=dump_prompt_value(synthesis))
        result, _ = await provider.generate_json(
            [ChatMessage(role="system", content=rendered), ChatMessage(role="user", content="Return the reusable creative profile now.")],
            CreativeProfile,
            temperature=0.3,
        )
        return result.model_dump()

    async def generate_framework_proposal(self, provider: LLMProvider, profile: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
        prompt = load_prompt("research/framework_proposal.yaml")
        rendered = render_prompt(
            prompt,
            project=dump_prompt_value(project),
            profile=dump_prompt_value(profile),
        )
        result, _ = await provider.generate_json(
            [ChatMessage(role="system", content=rendered), ChatMessage(role="user", content="Return the framework proposal now.")],
            InjectionProposal,
            temperature=0.55,
        )
        return result.model_dump()
