from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chapter import ChapterSummary
from app.db.models.memory import StoryMemory, TimelineEvent
from novel_engine.memory.models import ChapterHandoff, ChapterMemory, CharacterMemory, MemoryRecord, TimelineMemory, VectorRecord
from novel_engine.memory.service import MemoryService
from novel_engine.models.enums import EpistemicStatus, Importance, MemoryLayer, MemoryType
from novel_engine.models.story_state import StoryState
from novel_engine.style.anti_repetition import StyleHistory
from novel_engine.workflows.chapter_pipeline import CommitResult, ChapterGenerationPipeline


def _dedupe_key(kind: str, owner_id: uuid.UUID, suffix: str = "") -> str:
    return f"{kind}:{owner_id}:{suffix}"[:255]


def _fact_dedupe_key(kind: str, chapter_id: uuid.UUID, content: str) -> str:
    digest = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
    return _dedupe_key(kind, chapter_id, digest)


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
                    scene_handoffs=list(meta.get("scene_handoffs") or []),
                    chapter_handoff=ChapterHandoff.model_validate(meta["chapter_handoff"])
                    if isinstance(meta.get("chapter_handoff"), dict) else None,
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
        if kind == "story_state":
            memory.store.set_story_state(
                StoryState.model_validate((row.extra_metadata or {}).get("state") or {})
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
            character_name=(row.extra_metadata or {}).get("character_name"),
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
                # VectorRecord always uses the vector layer. Exclude the
                # source record's layer before overriding it, otherwise
                # Pydantic receives the same keyword twice.
                **record.model_dump(exclude={"layer"}),
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
            dedupe_key=_dedupe_key("chapter_memory", chapter_id),
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
                "scene_handoffs": [item.model_dump() for item in getattr(summary, "scene_handoffs", [])],
                "memory_validation": result.memory_validation,
                "chapter_handoff": result.handoff.model_dump(mode="json") if result.handoff else None,
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
                dedupe_key=_dedupe_key("character_state", chapter_id, state.name),
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
                dedupe_key=_fact_dedupe_key("fact", chapter_id, item.content),
                chapter_number=result.chapter.chapter_number,
                extra_metadata={
                    "kind": "fact",
                    "character_name": item.character_name,
                    "source_excerpt": item.source_excerpt,
                },
                known_by=list(item.known_by),
                unknown_to=list(item.unknown_to),
            )
        )
    state = pipeline.memory.store.story_state(project_id)
    if state is not None:
        state_row = await session.scalar(
            select(StoryMemory).where(
                StoryMemory.project_id == project_id,
                StoryMemory.dedupe_key == _dedupe_key("story_state", project_id),
            )
        )
        values = {
            "memory_type": MemoryType.FACT.value,
            "layer": MemoryLayer.GLOBAL.value,
            "epistemic_status": EpistemicStatus.CONFIRMED_FACT.value,
            "importance": Importance.HIGH.value,
            "source_chapter_id": chapter_id,
            "chapter_number": result.chapter.chapter_number,
            "content": f"Story state after chapter {result.chapter.chapter_number}",
            "tags": ["story_state"],
            "extra_metadata": {"kind": "story_state", "state": state.model_dump(mode="json")},
        }
        if state_row is None:
            session.add(StoryMemory(project_id=project_id, dedupe_key=_dedupe_key("story_state", project_id), **values))
        else:
            for key, value in values.items():
                setattr(state_row, key, value)
            flag_modified(state_row, "extra_metadata")
    for handoff in getattr(summary, "scene_handoffs", []):
        facts: dict[str, dict[str, list[str]]] = {}
        for character, items in (handoff.who_knows or {}).items():
            for fact in items:
                facts.setdefault(fact, {}).setdefault("known_by", []).append(character)
        for character, items in (handoff.unknown_to or {}).items():
            for fact in items:
                facts.setdefault(fact, {}).setdefault("unknown_to", []).append(character)
        for fact, visibility in facts.items():
            session.add(
                StoryMemory(
                    project_id=project_id,
                    memory_type=MemoryType.FACT.value,
                    layer=MemoryLayer.CHARACTER.value,
                    epistemic_status=EpistemicStatus.TENTATIVE_FACT.value,
                    importance=Importance.MEDIUM.value,
                    source_chapter_id=chapter_id,
                    chapter_number=result.chapter.chapter_number,
                    content=fact,
                    dedupe_key=_fact_dedupe_key("knowledge_boundary", chapter_id, fact),
                    known_by=visibility.get("known_by", []),
                    unknown_to=visibility.get("unknown_to", []),
                    tags=["scene_handoff", f"scene:{handoff.scene_number}"],
                    extra_metadata={
                        "kind": "knowledge_boundary",
                        "source_excerpt": handoff.source_excerpt,
                    },
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
            "narrative": {
                "fingerprints": dict(pipeline.style_history.narrative.fingerprints),
                "endings": dict(pipeline.style_history.narrative.endings),
            },
        },
    }
    if existing is None:
        session.add(
            StoryMemory(
                project_id=project_id,
                memory_type=MemoryType.FACT.value,
                layer=MemoryLayer.GLOBAL.value,
                epistemic_status=EpistemicStatus.TENTATIVE_FACT.value,
                content="style ledger",
                dedupe_key=_dedupe_key("style_ledger", project_id),
                tags=["style_ledger"],
                extra_metadata=payload,
            )
        )
    else:
        existing.extra_metadata = payload
        flag_modified(existing, "extra_metadata")
    # The route owns the transaction so approval and memory writes commit
    # together or roll back together.
    await session.flush()
