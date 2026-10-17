from __future__ import annotations

import uuid
from collections import defaultdict

from novel_engine.memory.models import (
    ChapterMemory,
    CharacterMemory,
    GlobalMemory,
    MemoryRecord,
    TimelineMemory,
    VectorRecord,
)
from novel_engine.models.story_state import StoryState
from novel_engine.models.enums import MemoryLayer


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self.globals: dict[uuid.UUID, GlobalMemory] = {}
        self.characters: dict[tuple[uuid.UUID, str], CharacterMemory] = {}
        self.timelines: dict[uuid.UUID, list[TimelineMemory]] = defaultdict(list)
        self.chapters: dict[uuid.UUID, dict[int, ChapterMemory]] = defaultdict(dict)
        self.records: dict[uuid.UUID, list[MemoryRecord]] = defaultdict(list)
        self.vectors: dict[uuid.UUID, list[VectorRecord]] = defaultdict(list)
        self.story_states: dict[uuid.UUID, StoryState] = {}

    def set_global(self, memory: GlobalMemory) -> None:
        self.globals[memory.project_id] = memory

    def get_global(self, project_id: uuid.UUID) -> GlobalMemory | None:
        return self.globals.get(project_id)

    def upsert_character(self, memory: CharacterMemory) -> None:
        self.characters[(memory.project_id, memory.name)] = memory

    def get_character(self, project_id: uuid.UUID, name: str) -> CharacterMemory | None:
        return self.characters.get((project_id, name))

    def characters_for(self, project_id: uuid.UUID, names: list[str]) -> list[CharacterMemory]:
        found: list[CharacterMemory] = []
        for name in names:
            item = self.get_character(project_id, name)
            if item is not None:
                found.append(item)
        return found

    def add_timeline(self, event: TimelineMemory) -> None:
        self.timelines[event.project_id].append(event)

    def timeline_for(self, project_id: uuid.UUID) -> list[TimelineMemory]:
        return sorted(self.timelines[project_id], key=lambda item: item.sequence)

    def add_chapter(self, memory: ChapterMemory) -> None:
        self.chapters[memory.project_id][memory.chapter_number] = memory

    def chapter(self, project_id: uuid.UUID, number: int) -> ChapterMemory | None:
        return self.chapters[project_id].get(number)

    def recent_chapters(self, project_id: uuid.UUID, before: int, window: int) -> list[ChapterMemory]:
        numbers = sorted(n for n in self.chapters[project_id] if n < before)
        selected = numbers[-window:]
        return [self.chapters[project_id][n] for n in selected]

    def all_chapters(self, project_id: uuid.UUID) -> list[ChapterMemory]:
        return [self.chapters[project_id][n] for n in sorted(self.chapters[project_id])]

    def add_record(self, record: MemoryRecord) -> MemoryRecord:
        self.records[record.project_id].append(record)
        return record

    def records_for(self, project_id: uuid.UUID, layer: MemoryLayer | None = None) -> list[MemoryRecord]:
        items = self.records[project_id]
        if layer is None:
            return list(items)
        return [item for item in items if item.layer is layer]

    def add_vector(self, record: VectorRecord) -> VectorRecord:
        self.vectors[record.project_id].append(record)
        return record

    def replace_vectors(self, project_id: uuid.UUID, records: list[VectorRecord]) -> None:
        self.vectors[project_id] = list(records)

    def vectors_for(self, project_id: uuid.UUID) -> list[VectorRecord]:
        return list(self.vectors[project_id])

    def set_story_state(self, state: StoryState) -> None:
        self.story_states[state.project_id] = state

    def story_state(self, project_id: uuid.UUID) -> StoryState | None:
        return self.story_states.get(project_id)

    def story_state_ledger(self, project_id: uuid.UUID) -> str:
        state = self.story_state(project_id)
        if state is None:
            return "No durable story state has been recorded yet."
        lines = [f"State after chapter {state.chapter_number}:"]
        for item in state.entities:
            lines.append(
                f"- entity {item.canonical_name} [{item.entity_type}] status={item.status}; "
                f"location={item.current_location or 'unknown'}; owner={item.owner or 'none'}"
            )
        for item in state.resources:
            lines.append(
                f"- resource {item.name}: {item.quantity:g} {item.unit}; "
                f"location={item.location or 'unknown'}; owner={item.owner or 'none'}"
            )
        for item in state.relationships:
            lines.append(f"- relationship {item.subject} {item.relation} {item.object} [{item.status}]")
        return "\n".join(lines)
