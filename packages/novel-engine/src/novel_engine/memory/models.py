from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from novel_engine.models.enums import EpistemicStatus, Importance, MemoryLayer, MemoryType


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    layer: MemoryLayer
    epistemic_status: EpistemicStatus
    memory_type: MemoryType = MemoryType.FACT
    importance: Importance = Importance.MEDIUM
    content: str
    chapter_number: int | None = None
    character_name: str | None = None
    location: str | None = None
    known_by: list[str] = Field(default_factory=list)
    unknown_to: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: str = "system"
    confirmed_by: str | None = None
    created_at: datetime = Field(default_factory=_now)


class VectorRecord(MemoryRecord):
    embedding: list[float]
    layer: MemoryLayer = MemoryLayer.VECTOR


class ChapterMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    chapter_number: int
    title: str
    summary: str
    key_events: list[str] = Field(default_factory=list)
    new_facts: list[str] = Field(default_factory=list)
    character_changes: list[str] = Field(default_factory=list)
    new_secrets: list[str] = Field(default_factory=list)
    resolved_secrets: list[str] = Field(default_factory=list)
    unresolved_hooks: list[str] = Field(default_factory=list)
    location: str | None = None
    characters: list[str] = Field(default_factory=list)
    arc: str | None = None


class TimelineMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    sequence: int
    chapter_number: int
    in_world_time: str
    title: str
    description: str
    location: str
    characters: list[str] = Field(default_factory=list)
    caused_by_sequence: int | None = None


class CharacterMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    name: str
    experiences: list[str] = Field(default_factory=list)
    knows: list[str] = Field(default_factory=list)
    does_not_know: list[str] = Field(default_factory=list)
    current_state: str = ""
    relationship_changes: list[str] = Field(default_factory=list)


class GlobalMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    world: str
    master_plot: str
    core_characters: list[str] = Field(default_factory=list)
    core_rules: list[str] = Field(default_factory=list)


class MemoryProposal(BaseModel):
    """LLM or human candidate. WritePolicy decides whether it becomes durable."""

    model_config = ConfigDict(extra="forbid")

    layer: MemoryLayer
    suggested_status: EpistemicStatus
    memory_type: MemoryType = MemoryType.FACT
    importance: Importance = Importance.MEDIUM
    content: str
    chapter_number: int | None = None
    character_name: str | None = None
    location: str | None = None
    known_by: list[str] = Field(default_factory=list)
    unknown_to: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: str = "llm"


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    chapter_number: int
    chapter_title: str
    pov: str
    location: str
    characters: list[str]
    locations: list[str] = Field(default_factory=list)
    current_arc: str | None = None
    chapter_goal: str = ""
    conflict: str = ""
    active_hooks: list[str] = Field(default_factory=list)
    recent_window: int = 3
    semantic_top_k: int = 5
    max_chapter_summaries: int = 6
    token_budget: int = 1800


class ContextPackage(BaseModel):
    """Compact writer context. Must never contain the whole novel."""

    model_config = ConfigDict(extra="forbid")

    world: str
    master_plot: str
    core_rules: list[str]
    character_slices: list[CharacterMemory]
    timeline_slices: list[TimelineMemory]
    recent_chapters: list[ChapterMemory]
    semantic_hits: list[MemoryRecord]
    unresolved_hooks: list[str]
    foreshadowing: list[str]
    forbidden_knowledge: dict[str, list[str]]
    token_estimate: int
    dropped_for_budget: int = 0

    def visible_text(self) -> str:
        parts = [self.world, self.master_plot, *self.core_rules, *self.unresolved_hooks, *self.foreshadowing]
        parts.extend(item.content for item in self.semantic_hits)
        for chapter in self.recent_chapters:
            parts.extend(
                [
                    chapter.title,
                    chapter.summary,
                    *chapter.key_events,
                    *chapter.new_facts,
                ]
            )
        for event in self.timeline_slices:
            parts.append(f"{event.location} {event.title} {event.description}")
        for character in self.character_slices:
            parts.extend(character.experiences)
            parts.extend(character.knows)
            parts.extend(character.does_not_know)
            parts.append(character.current_state)
            parts.extend(character.relationship_changes)
        return " ".join(part for part in parts if part)
