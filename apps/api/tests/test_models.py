import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import (
    Character,
    CharacterState,
    Chapter,
    ChapterRevision,
    NovelProject,
    Relationship,
    StoryMemory,
    restore_chapter_revision,
)
from app.db.models.constants import EMBEDDING_DIMENSIONS
from novel_engine.models.enums import ChapterStatus, CharacterRole, Importance, MemoryType


@pytest.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
            await engine.dispose()


async def _cleanup(session: AsyncSession, project: NovelProject) -> None:
    await session.delete(project)
    await session.commit()


@pytest.mark.asyncio
async def test_create_project_character_chapter_state_memory_and_relationship(
    db_session: AsyncSession,
) -> None:
    marker = uuid.uuid4().hex[:8]
    project = NovelProject(
        title=f"Rejected Luna {marker}",
        genre="werewolf_romance",
        tropes=["rejected_mate", "fated_mate", "revenge"],
        target_platform="alphanovel",
        logline="She was rejected. The pack will remember her name.",
    )
    db_session.add(project)
    await db_session.flush()

    heroine = Character(
        project_id=project.id,
        name="Aria Blackwood",
        role=CharacterRole.PROTAGONIST.value,
        species="werewolf",
        rank="omega",
        secrets=["hidden royal bloodline"],
        tropes=["rejected_mate", "powerful_female_lead", "hidden_identity"],
    )
    alpha = Character(
        project_id=project.id,
        name="Kael Thorn",
        aliases=["Alpha Kael"],
        role=CharacterRole.LOVE_INTEREST.value,
        species="werewolf",
        rank="alpha",
        tropes=["alpha_king"],
    )
    db_session.add_all([heroine, alpha])
    await db_session.flush()

    chapter = Chapter(
        project_id=project.id,
        chapter_number=1,
        title="The Rejection",
        status=ChapterStatus.DRAFT.value,
        content="Kael rejected Aria before the entire pack.",
        word_count=8,
    )
    db_session.add(chapter)
    await db_session.flush()

    revision_v1 = ChapterRevision(
        chapter_id=chapter.id,
        revision_number=1,
        content=chapter.content,
        word_count=chapter.word_count,
        change_summary="initial draft",
    )
    db_session.add(revision_v1)
    await db_session.flush()
    chapter.current_revision_id = revision_v1.id

    chapter.content = "Kael rejected Aria. She did not bow."
    chapter.word_count = 7
    revision_v2 = ChapterRevision(
        chapter_id=chapter.id,
        revision_number=2,
        content=chapter.content,
        word_count=chapter.word_count,
        change_summary="sharpen ending",
    )
    db_session.add(revision_v2)
    await db_session.flush()
    chapter.current_revision_id = revision_v2.id

    restored = await restore_chapter_revision(db_session, chapter, revision_v1)
    assert restored.revision_number == 3
    assert restored.restored_from_revision_id == revision_v1.id
    assert chapter.content == revision_v1.content
    assert chapter.current_revision_id == restored.id

    state = CharacterState(
        project_id=project.id,
        character_id=heroine.id,
        chapter_id=chapter.id,
        current_location="Moonridge Pack Hall",
        emotional_state="humiliated, furious",
        relationship_status="rejected mate",
        knowledge=["Kael chose another Luna"],
        secrets_known=[],
        powers=["unawakened royal aura"],
        health_status="uninjured",
        is_current=True,
    )
    rel = Relationship(
        project_id=project.id,
        source_character_id=heroine.id,
        target_character_id=alpha.id,
        relationship_type="rejected_mate",
        status="rejected",
        description="Public rejection before the pack.",
        started_chapter_id=chapter.id,
    )
    memory = StoryMemory(
        project_id=project.id,
        memory_type=MemoryType.EVENT.value,
        importance=Importance.CRITICAL.value,
        source_chapter_id=chapter.id,
        character_id=heroine.id,
        content="Aria is rejected by Kael in front of Moonridge Pack.",
        known_by=["Aria Blackwood", "Kael Thorn"],
        unknown_to=["the hidden royal council"],
        embedding=[0.01] * EMBEDDING_DIMENSIONS,
        extra_metadata={"tropes": ["rejected_mate"]},
    )
    db_session.add_all([state, rel, memory])
    await db_session.commit()

    loaded_project = await db_session.get(NovelProject, project.id)
    assert loaded_project is not None
    assert loaded_project.title.startswith("Rejected Luna")

    characters = (
        await db_session.scalars(
            select(Character).where(Character.project_id == project.id).order_by(Character.name)
        )
    ).all()
    assert {item.name for item in characters} == {"Aria Blackwood", "Kael Thorn"}
    assert next(item for item in characters if item.name == "Kael Thorn").aliases == ["Alpha Kael"]

    loaded_chapter = (
        await db_session.scalars(
            select(Chapter).where(
                Chapter.project_id == project.id,
                Chapter.chapter_number == 1,
            )
        )
    ).one()
    assert loaded_chapter.status == ChapterStatus.DRAFT.value
    assert loaded_chapter.content == revision_v1.content

    loaded_state = (
        await db_session.scalars(
            select(CharacterState).where(
                CharacterState.character_id == heroine.id,
                CharacterState.chapter_id == chapter.id,
            )
        )
    ).one()
    assert loaded_state.current_location == "Moonridge Pack Hall"
    assert loaded_state.emotional_state == "humiliated, furious"
    assert "Kael chose another Luna" in loaded_state.knowledge

    loaded_memory = (
        await db_session.scalars(
            select(StoryMemory).where(StoryMemory.project_id == project.id)
        )
    ).one()
    assert loaded_memory.memory_type == MemoryType.EVENT.value
    assert loaded_memory.embedding is not None
    assert len(loaded_memory.embedding) == EMBEDDING_DIMENSIONS
    assert loaded_memory.known_by == ["Aria Blackwood", "Kael Thorn"]
    assert loaded_memory.unknown_to == ["the hidden royal council"]

    mate_links = (
        await db_session.scalars(
            select(Relationship).where(
                Relationship.project_id == project.id,
                Relationship.source_character_id == heroine.id,
                Relationship.relationship_type == "rejected_mate",
            )
        )
    ).all()
    assert len(mate_links) == 1
    assert mate_links[0].target_character_id == alpha.id
    assert mate_links[0].status == "rejected"

    reverse_links = (
        await db_session.scalars(
            select(Relationship).where(Relationship.target_character_id == alpha.id)
        )
    ).all()
    assert len(reverse_links) == 1

    await _cleanup(db_session, loaded_project)
