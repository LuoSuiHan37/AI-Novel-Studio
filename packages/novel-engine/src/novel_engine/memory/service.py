from __future__ import annotations

import uuid

from novel_engine.memory.embeddings import LexicalEmbedder
from novel_engine.memory.models import (
    ChapterMemory,
    CharacterMemory,
    GlobalMemory,
    MemoryProposal,
    MemoryRecord,
    TimelineMemory,
    VectorRecord,
)
from novel_engine.memory.store import InMemoryMemoryStore
from novel_engine.memory.write_policy import apply_write_policy
from novel_engine.models.enums import EpistemicStatus, MemoryLayer, MemoryType


class MemoryService:
    def __init__(self, store: InMemoryMemoryStore | None = None, embedder: LexicalEmbedder | None = None) -> None:
        self.store = store or InMemoryMemoryStore()
        self.embedder = embedder or LexicalEmbedder()

    def set_global(
        self,
        project_id: uuid.UUID,
        *,
        world: str,
        master_plot: str,
        core_characters: list[str],
        core_rules: list[str],
        confirmed_by: str,
    ) -> GlobalMemory:
        memory = GlobalMemory(
            project_id=project_id,
            world=world,
            master_plot=master_plot,
            core_characters=core_characters,
            core_rules=core_rules,
        )
        self.store.set_global(memory)
        for rule in core_rules:
            self.write(
                project_id,
                MemoryProposal(
                    layer=MemoryLayer.GLOBAL,
                    suggested_status=EpistemicStatus.CONFIRMED_FACT,
                    memory_type=MemoryType.WORLD_RULE,
                    content=rule,
                    source="human",
                ),
                confirmed_by=confirmed_by,
            )
        return memory

    def write(
        self,
        project_id: uuid.UUID,
        proposal: MemoryProposal,
        *,
        confirmed_by: str | None = None,
    ) -> MemoryRecord:
        record = apply_write_policy(proposal, project_id, confirmed_by=confirmed_by)
        self.store.add_record(record)
        vector = VectorRecord(
            id=record.id,
            project_id=project_id,
            layer=MemoryLayer.VECTOR,
            epistemic_status=record.epistemic_status,
            memory_type=record.memory_type,
            importance=record.importance,
            content=record.content,
            chapter_number=record.chapter_number,
            character_name=record.character_name,
            location=record.location,
            known_by=list(record.known_by),
            unknown_to=list(record.unknown_to),
            tags=list(record.tags),
            source=record.source,
            confirmed_by=record.confirmed_by,
            embedding=self.embedder.embed(record.content),
        )
        self.store.add_vector(vector)
        return record

    def upsert_character(self, memory: CharacterMemory) -> None:
        self.store.upsert_character(memory)

    def add_timeline(self, event: TimelineMemory) -> None:
        self.store.add_timeline(event)
        self.write(
            event.project_id,
            MemoryProposal(
                layer=MemoryLayer.TIMELINE,
                suggested_status=EpistemicStatus.CONFIRMED_FACT,
                memory_type=MemoryType.EVENT,
                content=f"{event.in_world_time} {event.location}: {event.title}. {event.description}",
                chapter_number=event.chapter_number,
                location=event.location,
                known_by=list(event.characters),
                tags=["timeline"],
                source="human",
            ),
            confirmed_by="system",
        )

    def add_chapter(self, chapter: ChapterMemory, *, confirmed_by: str) -> None:
        self.store.add_chapter(chapter)
        blob = " ".join(
            [
                chapter.title,
                chapter.summary,
                " ".join(chapter.key_events),
                " ".join(chapter.new_facts),
                " ".join(chapter.unresolved_hooks),
            ]
        )
        self.write(
            chapter.project_id,
            MemoryProposal(
                layer=MemoryLayer.CHAPTER,
                suggested_status=EpistemicStatus.CONFIRMED_FACT,
                memory_type=MemoryType.PLOT,
                content=blob,
                chapter_number=chapter.chapter_number,
                location=chapter.location,
                known_by=list(chapter.characters),
                tags=["chapter", chapter.arc or ""],
                source="human",
            ),
            confirmed_by=confirmed_by,
        )
        for secret in chapter.new_secrets:
            self.write(
                chapter.project_id,
                MemoryProposal(
                    layer=MemoryLayer.CHAPTER,
                    suggested_status=EpistemicStatus.SECRET,
                    memory_type=MemoryType.SECRET,
                    content=secret,
                    chapter_number=chapter.chapter_number,
                    known_by=list(chapter.characters[:1]),
                    unknown_to=[name for name in chapter.characters[1:]],
                    tags=["secret"],
                    source="human",
                ),
                confirmed_by=confirmed_by,
            )
