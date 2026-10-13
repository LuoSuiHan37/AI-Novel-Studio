from __future__ import annotations

import uuid

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chapter import ChapterSummary
from app.db.models.memory import StoryMemory, TimelineEvent
from novel_engine.memory.models import ChapterMemory, CharacterMemory, MemoryRecord, TimelineMemory, VectorRecord
from novel_engine.memory.service import MemoryService
from novel_engine.models.enums import EpistemicStatus, Importance, MemoryLayer, MemoryType
from novel_engine.style.anti_repetition import StyleHistory
from novel_engine.workflows.chapter_pipeline import CommitResult, ChapterGenerationPipeline


async def hydrate_pipeline_memory(
    session: AsyncSession,
    project_id: uuid.UUID,
    memory: MemoryService,
) -> StyleHistory:
    rows = (
        await session.scalars(select(StoryMemory).where(StoryMemory.project_id == project_id))
    ).all()
    history = StyleHistory()
    for row in rows:
        meta = row.extra_metadata or {}
        kind = meta.get("kind")
        if kind == "style_ledger":
            history = StyleHistory.model_validate(meta.get("history") or {})
            continue
        if kind == "chapter_memory":
            memory.store.add_chapter(
                ChapterMemory(
                    project_id=project_id,
                    chapter_number=row.chapter_number or 0,
                    title=meta.get("title") or "",
                    summary=row.content,
                    key_events=list(meta.get("key_events") or []),
                    new_facts=list(meta.get("new_facts") or []),
                    character_changes=list(meta.get("character_changes") or []),
                    unresolved_hooks=list(meta.get("unresolved_hooks") or []),
                    location=row.location,
                    characters=list(meta.get("characters") or []),
                    arc=meta.get("arc"),
                )
            )
            continue
        if kind == "character_state":
            memory.store.upsert_character(
                CharacterMemory(
                    project_id=project_id,
                    name=meta.get("name") or "",
                    experiences=list(meta.get("experiences") or []),
                    knows=list(meta.get("knows") or []),
                    does_not_know=list(meta.get("does_not_know") or []),
                    current_state=row.content,
                    relationship_changes=list(meta.get("relationship_changes") or []),
                )
            )
            continue
        record = MemoryRecord(
            id=row.id,
            project_id=project_id,
            layer=MemoryLayer(row.layer),
            epistemic_status=EpistemicStatus(row.epistemic_status),
            memory_type=MemoryType(row.memory_type),
            importance=Importance(row.importance),
            content=row.content,
            chapter_number=row.chapter_number,
            location=row.location,
            known_by=list(row.known_by or []),
            unknown_to=list(row.unknown_to or []),
            tags=list(row.tags or []),
            source="system",
        )
        memory.store.add_record(record)
        memory.store.add_vector(
            VectorRecord(
                **record.model_dump(),
                layer=MemoryLayer.VECTOR,
                embedding=memory.embedder.embed(record.content),
            )
        )

    events = (
        await session.scalars(
            select(TimelineEvent).where(TimelineEvent.project_id == project_id).order_by(TimelineEvent.sequence)
        )
    ).all()
    for row in events:
        memory.store.add_timeline(
            TimelineMemory(
                id=row.id,
                project_id=project_id,
                sequence=row.sequence,
                chapter_number=row.sequence,
                in_world_time=row.in_world_time or "",
                title=row.title,
                description=row.description or "",
                location=row.location or "",
                characters=[],
            )
        )
    return history


async def persist_commit(
    session: AsyncSession,
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    pipeline: ChapterGenerationPipeline,
    result: CommitResult,
) -> None:
    summary = result.summary
    session.add(
        ChapterSummary(
            chapter_id=chapter_id,
            summary=summary.summary,
            key_events=list(summary.key_events),
            new_facts=list(summary.new_facts),
            character_changes=list(summary.character_changes),
            new_secrets=list(summary.new_secrets),
            resolved_secrets=list(summary.resolved_secrets),
            unresolved_hooks=list(summary.unresolved_hooks),
            location=summary.location,
        )
    )
    session.add(
        StoryMemory(
            project_id=project_id,
            memory_type=MemoryType.PLOT.value,
            layer=MemoryLayer.CHAPTER.value,
            epistemic_status=EpistemicStatus.CONFIRMED_FACT.value,
            importance=Importance.HIGH.value,
            source_chapter_id=chapter_id,
            chapter_number=result.chapter.chapter_number,
            location=summary.location,
            content=summary.summary,
            tags=["chapter"],
            extra_metadata={
                "kind": "chapter_memory",
                "title": summary.title,
                "key_events": list(summary.key_events),
                "new_facts": list(summary.new_facts),
                "character_changes": list(summary.character_changes),
                "unresolved_hooks": list(summary.unresolved_hooks),
                "characters": list(result.timeline.characters),
                "arc": result.chapter.story_arc_id and str(result.chapter.story_arc_id),
            },
        )
    )
    for state in result.character_states:
        session.add(
            StoryMemory(
                project_id=project_id,
                memory_type=MemoryType.CHARACTER.value,
                layer=MemoryLayer.CHARACTER.value,
                epistemic_status=EpistemicStatus.CONFIRMED_FACT.value,
                content=state.current_state,
                chapter_number=result.chapter.chapter_number,
                tags=["character_state"],
                extra_metadata={
                    "kind": "character_state",
                    "name": state.name,
                    "experiences": list(state.experiences),
                    "knows": list(state.knows),
                    "does_not_know": list(state.does_not_know),
                    "relationship_changes": list(state.relationship_changes),
                },
            )
        )
    for item in result.memory.memories:
        session.add(
            StoryMemory(
                project_id=project_id,
                memory_type=item.memory_type.value,
                layer=(MemoryLayer.CHARACTER if item.character_name else MemoryLayer.CHAPTER).value,
                epistemic_status=EpistemicStatus.TENTATIVE_FACT.value,
                importance=item.importance.value,
                content=item.content,
                chapter_number=result.chapter.chapter_number,
                extra_metadata={"kind": "fact"},
            )
        )
    session.add(
        TimelineEvent(
            project_id=project_id,
            chapter_id=chapter_id,
            sequence=result.timeline.sequence,
            in_world_time=result.timeline.in_world_time,
            title=result.timeline.title,
            description=result.timeline.description,
            location=result.timeline.location,
            involved_character_ids=list(result.timeline.characters),
        )
    )
    rows = (
        await session.scalars(select(StoryMemory).where(StoryMemory.project_id == project_id))
    ).all()
    existing = next((row for row in rows if (row.extra_metadata or {}).get("kind") == "style_ledger"), None)
    payload = {
        "kind": "style_ledger",
        "history": {
            "phrases": dict(pipeline.style_history.phrases),
            "scene_patterns": dict(pipeline.style_history.scene_patterns),
            "conflicts": dict(pipeline.style_history.conflicts),
            "dialogue_patterns": dict(pipeline.style_history.dialogue_patterns),
        },
    }
    if existing is None:
        session.add(
            StoryMemory(
                project_id=project_id,
                memory_type=MemoryType.FACT.value,
                layer=MemoryLayer.GLOBAL.value,
                epistemic_status=EpistemicStatus.CONFIRMED_FACT.value,
                content="style ledger",
                tags=["style_ledger"],
                extra_metadata=payload,
            )
        )
    else:
        existing.extra_metadata = payload
        flag_modified(existing, "extra_metadata")
    await session.commit()
