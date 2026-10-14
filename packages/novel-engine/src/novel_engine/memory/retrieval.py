from __future__ import annotations

from novel_engine.memory.embeddings import cosine_similarity, estimate_tokens
from novel_engine.memory.knowledge import build_forbidden_map, filter_records_for_pov
from novel_engine.memory.models import (
    ChapterMemory,
    ContextPackage,
    MemoryRecord,
    RetrievalRequest,
    TimelineMemory,
)
from novel_engine.memory.store import InMemoryMemoryStore
from novel_engine.models.enums import EpistemicStatus, MemoryLayer, MemoryType


class RetrievalPipeline:
    """Selective retrieval: recent window + targeted character/timeline + semantic top-k."""

    def __init__(self, store: InMemoryMemoryStore, embedder) -> None:
        self._store = store
        self._embedder = embedder

    def retrieve(self, request: RetrievalRequest) -> ContextPackage:
        global_memory = self._store.get_global(request.project_id)
        world = global_memory.world if global_memory else ""
        master_plot = global_memory.master_plot if global_memory else ""
        core_rules = list(global_memory.core_rules) if global_memory else []

        recent = self._store.recent_chapters(
            request.project_id, request.chapter_number, request.recent_window
        )
        characters = self._store.characters_for(request.project_id, request.characters)
        timeline = self._select_timeline(request)
        all_records = self._store.records_for(request.project_id)
        forbidden = build_forbidden_map(all_records, request.characters)

        semantic = self._semantic_hits(request)
        semantic = filter_records_for_pov(semantic, request.pov)

        hooks = self._unresolved_hooks(request, recent)
        foreshadow = [
            item.content
            for item in all_records
            if "foreshadow" in item.tags or item.memory_type is MemoryType.HOOK
        ]
        if request.active_hooks:
            for hook in request.active_hooks:
                if hook not in hooks:
                    hooks.append(hook)

        related_chapters = self._related_chapters(request, recent)
        world_rules = [
            item.content
            for item in all_records
            if item.memory_type is MemoryType.WORLD_RULE
            or (item.layer is MemoryLayer.GLOBAL and item.epistemic_status is EpistemicStatus.CONFIRMED_FACT)
        ]
        for rule in world_rules:
            if rule not in core_rules:
                core_rules.append(rule)

        package = ContextPackage(
            world=world,
            master_plot=master_plot,
            core_rules=core_rules,
            character_slices=characters,
            timeline_slices=timeline,
            recent_chapters=related_chapters,
            semantic_hits=semantic,
            unresolved_hooks=hooks[:12],
            foreshadowing=foreshadow[:8],
            forbidden_knowledge=forbidden,
            token_estimate=0,
        )
        return self._fit_budget(package, request.token_budget)

    def _select_timeline(self, request: RetrievalRequest) -> list[TimelineMemory]:
        events = self._store.timeline_for(request.project_id)
        names = set(request.characters)
        locations = {request.location, *request.locations}
        scored: list[tuple[int, TimelineMemory]] = []
        for event in events:
            score = 0
            if event.location in locations:
                score += 3
            if names.intersection(event.characters):
                score += 2
            if abs(event.chapter_number - request.chapter_number) <= 3:
                score += 1
            if score:
                scored.append((score, event))
        scored.sort(key=lambda item: (-item[0], item[1].sequence))
        return [event for _, event in scored[:8]]

    def _semantic_hits(self, request: RetrievalRequest) -> list[MemoryRecord]:
        query = " ".join(
            [
                request.chapter_title,
                request.location,
                " ".join(request.characters),
                request.current_arc or "",
                request.chapter_goal,
                request.conflict,
                " ".join(request.active_hooks),
            ]
        )
        query_vec = self._embedder.embed(query)
        ranked: list[tuple[float, MemoryRecord]] = []
        for vector in self._store.vectors_for(request.project_id):
            score = cosine_similarity(query_vec, vector.embedding)
            if score <= 0.08:
                continue
            ranked.append((score, vector))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in ranked[: request.semantic_top_k]]

    def _related_chapters(
        self, request: RetrievalRequest, recent: list[ChapterMemory]
    ) -> list[ChapterMemory]:
        by_number = {item.chapter_number: item for item in recent}
        names = set(request.characters)
        locations = {request.location, *request.locations}
        for chapter in self._store.all_chapters(request.project_id):
            if chapter.chapter_number >= request.chapter_number:
                continue
            if chapter.chapter_number in by_number:
                continue
            loc_hit = chapter.location in locations if chapter.location else False
            char_hit = bool(names.intersection(chapter.characters))
            hook_hit = bool(set(request.active_hooks).intersection(chapter.unresolved_hooks))
            if loc_hit and (char_hit or hook_hit or chapter.location == request.location):
                by_number[chapter.chapter_number] = chapter
        ordered = [by_number[n] for n in sorted(by_number)]
        return ordered[-request.max_chapter_summaries :]

    def _unresolved_hooks(self, request: RetrievalRequest, recent: list[ChapterMemory]) -> list[str]:
        seen: list[str] = []
        for chapter in self._store.all_chapters(request.project_id):
            if chapter.chapter_number >= request.chapter_number:
                continue
            for hook in chapter.unresolved_hooks:
                if hook not in seen:
                    seen.append(hook)
        return seen

    def _fit_budget(self, package: ContextPackage, budget: int) -> ContextPackage:
        dropped = 0
        semantic = list(package.semantic_hits)
        chapters = list(package.recent_chapters)
        timeline = list(package.timeline_slices)

        def estimate() -> int:
            parts = [
                package.world,
                package.master_plot,
                *package.core_rules,
                *package.unresolved_hooks,
                *package.foreshadowing,
                *[item.content for item in semantic],
                *[item.summary for item in chapters],
                *[item.description for item in timeline],
            ]
            for character in package.character_slices:
                parts.extend(character.experiences[-4:])
                parts.extend(character.knows[-4:])
                parts.append(character.current_state)
            return estimate_tokens(*parts)

        while estimate() > budget and semantic:
            semantic.pop()
            dropped += 1
        while estimate() > budget and len(chapters) > 1:
            chapters.pop(0)
            dropped += 1
        while estimate() > budget and timeline:
            timeline.pop()
            dropped += 1
        fitted = package.model_copy(
            update={
                "semantic_hits": semantic,
                "recent_chapters": chapters,
                "timeline_slices": timeline,
                "dropped_for_budget": dropped,
            }
        )
        return fitted.model_copy(update={"token_estimate": estimate()})
