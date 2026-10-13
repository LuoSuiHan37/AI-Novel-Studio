from __future__ import annotations

import uuid

import pytest

from novel_engine.agents.contracts import WriterContext, WriterInput
from novel_engine.agents.writer import WriterAgent
from novel_engine.domain.errors import InvalidStateError, KnowledgeLeakError
from novel_engine.memory.knowledge import check_prose_knowledge
from novel_engine.memory.models import (
    ChapterMemory,
    CharacterMemory,
    MemoryProposal,
    RetrievalRequest,
    TimelineMemory,
)
from novel_engine.memory.retrieval import RetrievalPipeline
from novel_engine.memory.service import MemoryService
from novel_engine.models.enums import EpistemicStatus, MemoryLayer, MemoryType
from test_agents import ScriptedJsonProvider, _bible, _heroine, _plan

SECRET = "Aria is the lost Nightshade princess"
PROJECT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _chapters() -> list[dict]:
    return [
        {
            "n": 1,
            "title": "Public Rejection",
            "loc": "Moonridge Pack Hall",
            "arc": "Rejection",
            "chars": ["Aria", "Kael"],
            "summary": "Kael rejects Aria as mate before the assembled pack in Moonridge Pack Hall.",
            "events": ["Kael severs the mate claim", "Aria is stripped of Luna rank"],
            "hooks": ["Who called her princess?"],
        },
        {
            "n": 2,
            "title": "Exile Gate",
            "loc": "Moonridge Pack Hall",
            "arc": "Rejection",
            "chars": ["Aria", "Kael"],
            "summary": "Guards march Aria from Pack Hall. Kael does not look back.",
            "events": ["Aria leaves Moonridge lands"],
            "hooks": ["Who called her princess?"],
        },
        {
            "n": 3,
            "title": "First Night Alone",
            "loc": "Blackpine Forest",
            "arc": "Exile",
            "chars": ["Aria"],
            "summary": "Aria sleeps under Blackpine Forest and feels the broken bond ache.",
            "events": ["Bond pain spikes"],
            "hooks": ["Who called her princess?"],
        },
        {
            "n": 4,
            "title": "Silver Crest Burn",
            "loc": "Blackpine Forest",
            "arc": "Exile",
            "chars": ["Aria"],
            "summary": "A hidden crest on Aria's wrist burns when moonlight hits it. Foreshadow of royal blood.",
            "events": ["Crest burns under moonlight"],
            "hooks": ["What is the silver crest?"],
        },
        {
            "n": 5,
            "title": "River Crossing",
            "loc": "Blackpine Forest",
            "arc": "Exile",
            "chars": ["Aria"],
            "summary": "Aria fords the icy river to leave pack hunters behind.",
            "events": ["Aria crosses the border river"],
            "hooks": ["What is the silver crest?"],
        },
        {
            "n": 6,
            "title": "Chanterelle Camp",
            "loc": "Mushroom Hollow",
            "arc": "Survival filler",
            "chars": ["Aria"],
            "summary": "Aria gathers chanterelle mushrooms and dries morels over a tiny fire in Mushroom Hollow.",
            "events": ["Forages chanterelles and morels"],
            "hooks": [],
        },
        {
            "n": 7,
            "title": "Spore Fever",
            "loc": "Mushroom Hollow",
            "arc": "Survival filler",
            "chars": ["Aria"],
            "summary": "Puffball spores make Aria feverish. She catalogs toadstools to stay awake.",
            "events": ["Spore fever"],
            "hooks": [],
        },
        {
            "n": 8,
            "title": "Truffle Trade",
            "loc": "Mushroom Hollow",
            "arc": "Survival filler",
            "chars": ["Aria"],
            "summary": "A passing fox-shifter trades bread for black truffles. No pack politics.",
            "events": ["Truffle barter"],
            "hooks": [],
        },
        {
            "n": 9,
            "title": "Rumor of a Pup",
            "loc": "Waystation",
            "arc": "Secret baby rumor",
            "chars": ["Aria"],
            "summary": "Waystation wolves whisper that the rejected Luna carries Kael's secret baby. Aria knows it is a rumor.",
            "events": ["Secret-baby rumor spreads"],
            "hooks": ["Is the pregnancy rumor true?"],
        },
        {
            "n": 10,
            "title": "Healer's Tent",
            "loc": "Waystation",
            "arc": "Secret baby rumor",
            "chars": ["Aria"],
            "summary": "A healer offers a tonic. Aria refuses. The rumor grows louder.",
            "events": ["Aria refuses tonic"],
            "hooks": ["Is the pregnancy rumor true?"],
        },
        {
            "n": 11,
            "title": "Letter Unopened",
            "loc": "Waystation",
            "arc": "Secret baby rumor",
            "chars": ["Aria"],
            "summary": "An unsigned letter claims Kael wants the child. Aria burns it unread.",
            "events": ["Letter burned"],
            "hooks": ["Is the pregnancy rumor true?"],
        },
        {
            "n": 12,
            "title": "Rumor Dies",
            "loc": "Waystation",
            "arc": "Secret baby rumor",
            "chars": ["Aria"],
            "summary": "Aria's cycle proves the secret-baby rumor false. She files it as rumor, not fact.",
            "events": ["Rumor disproved to Aria"],
            "hooks": [],
        },
        {
            "n": 13,
            "title": "Nightshade Sigil",
            "loc": "Ruined Chapel",
            "arc": "Hidden identity",
            "chars": ["Aria"],
            "summary": "Chapel stone matches the silver crest. Aria learns a fragment of Nightshade history.",
            "events": ["Crest matches Nightshade sigil"],
            "hooks": ["What is the silver crest?", "Who called her princess?"],
        },
        {
            "n": 14,
            "title": "Hidden Name",
            "loc": "Ruined Chapel",
            "arc": "Hidden identity",
            "chars": ["Aria"],
            "summary": "A dying priest names her princess of Nightshade. Aria keeps the secret.",
            "events": ["Priest names her princess"],
            "hooks": ["Who called her princess?"],
        },
        {
            "n": 15,
            "title": "Mask of a Rogue",
            "loc": "Border Town",
            "arc": "Hidden identity",
            "chars": ["Aria"],
            "summary": "Aria hides her crest under gloves and works as a rogue scout.",
            "events": ["Aria adopts a rogue alias"],
            "hooks": ["Who called her princess?"],
        },
        {
            "n": 16,
            "title": "Kael Hears Nothing",
            "loc": "Moonridge Pack Hall",
            "arc": "Hidden identity",
            "chars": ["Kael"],
            "summary": "Kael sits in Pack Hall and hears only that Aria survived the forest. He does not hear princess.",
            "events": ["Kael learns Aria lives"],
            "hooks": ["Who called her princess?"],
        },
        {
            "n": 17,
            "title": "Revenge Ledger",
            "loc": "Rogue Camp",
            "arc": "Revenge",
            "chars": ["Aria"],
            "summary": "Aria lists every elder who laughed at the rejection. Revenge planning begins.",
            "events": ["Revenge list written"],
            "hooks": ["Will Aria return to Pack Hall?"],
        },
        {
            "n": 18,
            "title": "Allies of Dust",
            "loc": "Rogue Camp",
            "arc": "Revenge",
            "chars": ["Aria"],
            "summary": "Exiled wolves swear to walk with her if she challenges Kael.",
            "events": ["Rogues pledge"],
            "hooks": ["Will Aria return to Pack Hall?"],
        },
        {
            "n": 19,
            "title": "Challenge Drafted",
            "loc": "Rogue Camp",
            "arc": "Revenge",
            "chars": ["Aria"],
            "summary": "Aria drafts a formal challenge to reclaim standing in Moonridge Pack Hall.",
            "events": ["Challenge letter drafted"],
            "hooks": ["Will Aria return to Pack Hall?"],
        },
        {
            "n": 20,
            "title": "March Begins",
            "loc": "Border Road",
            "arc": "Revenge",
            "chars": ["Aria"],
            "summary": "The rogue column leaves camp toward Moonridge.",
            "events": ["March on Moonridge starts"],
            "hooks": ["Will Aria return to Pack Hall?"],
        },
        {
            "n": 21,
            "title": "Gates in Sight",
            "loc": "Moonridge Gates",
            "arc": "Return",
            "chars": ["Aria"],
            "summary": "Aria sees Pack Hall roofs. She still hides the Nightshade secret from Kael.",
            "events": ["Aria reaches the gates"],
            "hooks": ["Who called her princess?", "Will Aria return to Pack Hall?"],
        },
        {
            "n": 22,
            "title": "Return Threshold",
            "loc": "Moonridge Pack Hall",
            "arc": "Return",
            "chars": ["Aria", "Kael"],
            "summary": "Placeholder: not yet written.",
            "events": [],
            "hooks": ["Who called her princess?"],
        },
        {
            "n": 23,
            "title": "Future Duel",
            "loc": "Moonridge Pack Hall",
            "arc": "Return",
            "chars": ["Aria", "Kael"],
            "summary": "Not yet written.",
            "events": [],
            "hooks": [],
        },
        {
            "n": 24,
            "title": "Future Bond",
            "loc": "Moonridge Pack Hall",
            "arc": "Return",
            "chars": ["Aria", "Kael"],
            "summary": "Not yet written.",
            "events": [],
            "hooks": [],
        },
    ]


def _seed() -> MemoryService:
    service = MemoryService()
    service.set_global(
        PROJECT_ID,
        world="Moonridge Pack under Alpha King Kael. Mate bonds can be publicly rejected.",
        master_plot="Rejected mate Aria survives exile, learns a royal secret, and returns to Pack Hall.",
        core_characters=["Aria", "Kael"],
        core_rules=["A public rejection before the pack severs Luna rank."],
        confirmed_by="human",
    )
    service.upsert_character(
        CharacterMemory(
            project_id=PROJECT_ID,
            name="Aria",
            experiences=["Rejected in Pack Hall", "Exiled through Blackpine Forest", "Learned Nightshade name"],
            knows=[SECRET, "The secret-baby rumor is false"],
            does_not_know=["Whether Kael still feels the bond"],
            current_state="At Moonridge gates, armored, unclaimed",
            relationship_changes=["Mate bond rejected", "Kael is now a target and a wound"],
        )
    )
    service.upsert_character(
        CharacterMemory(
            project_id=PROJECT_ID,
            name="Kael",
            experiences=["Rejected Aria in Pack Hall", "Ruled as Alpha King"],
            knows=["Aria survived the forest"],
            does_not_know=[SECRET],
            current_state="On the Pack Hall dais, restless",
            relationship_changes=["Publicly discarded his fated mate"],
        )
    )
    service.write(
        PROJECT_ID,
        MemoryProposal(
            layer=MemoryLayer.GLOBAL,
            suggested_status=EpistemicStatus.SECRET,
            memory_type=MemoryType.SECRET,
            content=SECRET,
            known_by=["Aria"],
            unknown_to=["Kael"],
            tags=["hidden-identity"],
            source="human",
        ),
        confirmed_by="human",
    )
    service.write(
        PROJECT_ID,
        MemoryProposal(
            layer=MemoryLayer.CHAPTER,
            suggested_status=EpistemicStatus.RUMOR,
            memory_type=MemoryType.PLOT,
            content="Waystation wolves claim Aria carries Kael's secret baby",
            character_name="Aria",
            location="Waystation",
            chapter_number=9,
            tags=["rumor"],
            source="human",
        ),
        confirmed_by="human",
    )
    service.write(
        PROJECT_ID,
        MemoryProposal(
            layer=MemoryLayer.GLOBAL,
            suggested_status=EpistemicStatus.CONFIRMED_FACT,
            memory_type=MemoryType.HOOK,
            content="A stranger called Aria princess during the rejection",
            tags=["foreshadow", "hook"],
            source="human",
        ),
        confirmed_by="human",
    )
    for row in _chapters():
        if row["n"] >= 22:
            continue
        service.add_chapter(
            ChapterMemory(
                project_id=PROJECT_ID,
                chapter_number=row["n"],
                title=row["title"],
                summary=row["summary"],
                key_events=row["events"],
                new_facts=row["events"],
                character_changes=[],
                unresolved_hooks=row["hooks"],
                location=row["loc"],
                characters=row["chars"],
                arc=row["arc"],
            ),
            confirmed_by="human",
        )
        service.add_timeline(
            TimelineMemory(
                project_id=PROJECT_ID,
                sequence=row["n"],
                chapter_number=row["n"],
                in_world_time=f"Day {row['n']}",
                title=row["title"],
                description=row["summary"],
                location=row["loc"],
                characters=row["chars"],
                caused_by_sequence=None if row["n"] == 1 else row["n"] - 1,
            )
        )
    return service


def _retrieve(service: MemoryService, pov: str = "Kael") -> object:
    pipeline = RetrievalPipeline(service.store, service.embedder)
    return pipeline.retrieve(
        RetrievalRequest(
            project_id=PROJECT_ID,
            chapter_number=22,
            chapter_title="Return to Moonridge Pack Hall",
            pov=pov,
            location="Moonridge Pack Hall",
            characters=["Aria", "Kael"],
            locations=["Moonridge Pack Hall"],
            current_arc="Return",
            chapter_goal="Aria re-enters Pack Hall and faces Kael without revealing Nightshade blood",
            conflict="Rejected mate returns to challenge the Alpha King",
            active_hooks=["Who called her princess?", "Will Aria return to Pack Hall?"],
            recent_window=3,
            semantic_top_k=5,
            max_chapter_summaries=6,
            token_budget=1800,
        )
    )


def test_llm_cannot_confirm_global_canon() -> None:
    service = MemoryService()
    with pytest.raises(InvalidStateError, match="global canon"):
        service.write(
            PROJECT_ID,
            MemoryProposal(
                layer=MemoryLayer.GLOBAL,
                suggested_status=EpistemicStatus.CONFIRMED_FACT,
                content="Kael is secretly a vampire",
                source="llm",
            ),
        )


def test_llm_confirmed_fact_is_demoted() -> None:
    service = MemoryService()
    record = service.write(
        PROJECT_ID,
        MemoryProposal(
            layer=MemoryLayer.CHAPTER,
            suggested_status=EpistemicStatus.CONFIRMED_FACT,
            content="Aria smiled once in the forest",
            source="llm",
        ),
    )
    assert record.epistemic_status is EpistemicStatus.TENTATIVE_FACT
    assert record.confirmed_by is None


def test_rumor_cannot_enter_global_memory() -> None:
    service = MemoryService()
    with pytest.raises(InvalidStateError, match="rumors"):
        service.write(
            PROJECT_ID,
            MemoryProposal(
                layer=MemoryLayer.GLOBAL,
                suggested_status=EpistemicStatus.RUMOR,
                content="The pack says Aria is pregnant",
                source="human",
            ),
            confirmed_by="editor",
        )


def test_human_can_confirm_world_rule() -> None:
    service = MemoryService()
    record = service.write(
        PROJECT_ID,
        MemoryProposal(
            layer=MemoryLayer.GLOBAL,
            suggested_status=EpistemicStatus.CONFIRMED_FACT,
            memory_type=MemoryType.WORLD_RULE,
            content="Silver burns false mates",
            source="human",
        ),
        confirmed_by="editor",
    )
    assert record.epistemic_status is EpistemicStatus.CONFIRMED_FACT


def test_retrieval_is_selective_across_twenty_four_chapters() -> None:
    service = _seed()
    assert len(service.store.all_chapters(PROJECT_ID)) == 21
    package = _retrieve(service, pov="Kael")
    text = package.visible_text().lower()
    numbers = {item.chapter_number for item in package.recent_chapters}
    assert package.token_estimate <= 1800
    assert len(package.recent_chapters) <= 6
    assert len(package.semantic_hits) <= 5
    assert 1 in numbers or "rejection" in text
    assert "pack hall" in text
    assert "chanterelle" not in text
    assert "morels" not in text
    assert "toadstools" not in text
    assert "truffles" not in text
    assert 6 not in numbers
    assert 7 not in numbers
    assert 8 not in numbers
    assert SECRET not in [hit.content for hit in package.semantic_hits]
    assert SECRET in package.forbidden_knowledge["Kael"]
    assert SECRET not in package.forbidden_knowledge["Aria"]
    assert any("princess" in hook.lower() for hook in package.unresolved_hooks)
    assert any("pack hall" in event.location.lower() for event in package.timeline_slices)
    assert "public rejection" in " ".join(package.core_rules).lower() or package.core_rules


def test_kael_pov_cannot_state_hidden_identity() -> None:
    service = _seed()
    package = _retrieve(service, pov="Kael")
    with pytest.raises(KnowledgeLeakError, match="Kael"):
        check_prose_knowledge(
            f"Kael smiled because he suddenly understood that {SECRET}.",
            "Kael",
            package,
        )


@pytest.mark.asyncio
async def test_writer_blocks_knowledge_leak() -> None:
    provider = ScriptedJsonProvider(
        [
            {
                "title": "Return",
                "prose": f"Kael knew the truth: {SECRET}.",
                "word_count": 8,
                "used_character_names": ["Aria Blackwood"],
                "planted_hooks": [],
            }
        ]
    )
    plan = _plan().model_copy(update={"pov": "Kael", "chapter_number": 22})
    context = WriterContext(
        story_bible=_bible(),
        world_rules=["Public rejection severs rank."],
        characters=[_heroine()],
        chapter_plan=plan,
        forbidden_knowledge={"Kael": [SECRET]},
    )
    with pytest.raises(KnowledgeLeakError, match="Kael"):
        await WriterAgent(provider).run(WriterInput(context=context))
