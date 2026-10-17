from __future__ import annotations

from novel_engine.agents.contracts import (
    ChapterPlannerOutput,
    CharacterAgentOutput,
    MemorySnippet,
    OutlineArc,
    OutlineBeat,
    OutlineOutput,
    SceneDraft,
    StoryArchitectOutput,
    WorldAgentOutput,
    WorldRuleDraft,
    WriterContext,
)
from novel_engine.memory.models import ContextPackage
from novel_engine.models.entities import (
    ChapterPlan,
    Character,
    MasterPlot,
    ScenePlan,
    StoryArc,
    StoryBible,
    WorldBible,
)


def story_bible_to_architect(bible: StoryBible) -> StoryArchitectOutput:
    return StoryArchitectOutput(
        premise=bible.premise,
        theme=bible.theme,
        tone=bible.tone,
        narrative_style=bible.narrative_style,
        pov=bible.pov,
        tense=bible.tense,
        romance_level=bible.romance_level,
        violence_level=bible.violence_level,
        heat_level=bible.heat_level,
        logline=bible.logline or bible.premise,
        synopsis=bible.synopsis or bible.premise,
    )


def character_to_agent(character: Character) -> CharacterAgentOutput:
    return CharacterAgentOutput(
        name=character.name,
        aliases=list(character.aliases),
        role=character.role,
        personality=character.personality,
        background=character.background,
        goal=character.goal,
        motivation=character.motivation,
        fear=character.fear,
        secret=character.secret,
        strength=character.strength,
        weakness=character.weakness,
        internal_conflict=character.internal_conflict,
        external_conflict=character.external_conflict,
        speech_style=character.speech_style,
        character_arc=character.character_arc,
        tropes=list(character.tropes),
    )


def world_bible_to_agent(world: WorldBible) -> WorldAgentOutput:
    return WorldAgentOutput(
        name=world.name,
        summary=world.summary,
        geography=world.geography or "",
        factions=list(world.factions),
        rules=[
            WorldRuleDraft(
                name=rule.name,
                category=rule.category,
                description=rule.description,
                is_hard_constraint=rule.is_hard_constraint,
            )
            for rule in world.rules
        ],
    )


def plan_to_agent(plan: ChapterPlan, scenes: list[ScenePlan]) -> ChapterPlannerOutput:
    return ChapterPlannerOutput(
        chapter_number=plan.chapter_number,
        chapter_title=plan.chapter_title,
        pov=plan.pov,
        location=plan.location,
        characters=list(plan.characters),
        chapter_goal=plan.chapter_goal,
        conflict=plan.conflict,
        emotional_arc=plan.emotional_arc,
        new_information=plan.new_information,
        reveal=plan.reveal,
        foreshadowing=plan.foreshadowing,
        setup=plan.setup,
        payoff=plan.payoff,
        cliffhanger=plan.cliffhanger,
        target_word_count=plan.target_word_count,
        target_word_min=plan.target_word_min,
        target_word_max=plan.target_word_max,
        scenes=[
            SceneDraft(
                scene_number=item.scene_number,
                location=item.location,
                characters=list(item.characters),
                goal=item.goal,
                conflict=item.conflict,
                turning_point=item.turning_point,
                dialogue_goal=item.dialogue_goal,
                emotion=item.emotion,
                information_revealed=item.information_revealed,
                ending=item.ending,
                protagonist_want=item.protagonist_want,
                active_pressure=item.active_pressure,
                choice_and_cost=item.choice_and_cost,
                irreversible_change=item.irreversible_change,
                environment_pressure=item.environment_pressure,
                target_word_count=item.target_word_count,
                target_word_min=item.target_word_min,
                target_word_max=item.target_word_max,
            )
            for item in scenes
        ],
    )


def plot_to_outline(plot: MasterPlot, arcs: list[StoryArc]) -> OutlineOutput:
    return OutlineOutput(
        title=plot.title,
        structure=plot.structure,
        summary=plot.summary,
        beats=[
            OutlineBeat(name=item.name, description=item.description, chapter_hint=item.chapter_hint)
            for item in plot.beats
        ],
        arcs=[
            OutlineArc(
                title=arc.title,
                sequence=arc.sequence,
                summary=arc.summary,
                start_chapter_number=arc.start_chapter_number or 1,
                end_chapter_number=arc.end_chapter_number or 1,
            )
            for arc in arcs
        ],
    )


def package_brief(package: ContextPackage) -> str:
    return package.visible_text()[:4000]


def snippets_from_package(package: ContextPackage) -> list[MemorySnippet]:
    from novel_engine.models.enums import Importance, MemoryType

    items: list[MemorySnippet] = []
    for record in package.semantic_hits[:8]:
        items.append(
            MemorySnippet(
                memory_type=record.memory_type,
                importance=record.importance,
                content=record.content,
            )
        )
    for chapter in package.recent_chapters[-3:]:
        items.append(
            MemorySnippet(
                memory_type=MemoryType.PLOT,
                importance=Importance.HIGH,
                content=f"Ch{chapter.chapter_number} {chapter.title}: {chapter.summary}",
            )
        )
    return items


def _writer_creative_profile(profile: dict | None) -> dict:
    """Keep writer-facing guidance, excluding research dumps and future plans."""
    if not isinstance(profile, dict):
        return {}
    allowed = (
        "style_guide",
        "anti_ai_rules",
        "rhythm_controls",
        "hard_constraints",
        "chapter_plan_rules",
        "relationship_progression",
        "originality_notes",
        "novel_constitution",
        "environment_bible",
        "relationship_ledger",
    )
    result = {key: profile[key] for key in allowed if key in profile}
    # Keep the active prompt compact; long research/profile artifacts are not
    # chapter instructions and often turn into accidental writing formulas.
    for key in ("anti_ai_rules", "rhythm_controls", "hard_constraints", "chapter_plan_rules", "relationship_progression"):
        if isinstance(result.get(key), list):
            result[key] = [str(item) for item in result[key][:8]]
    return result


def build_writer_context(
    *,
    bible: StoryBible,
    world: WorldBible | None,
    characters: list[Character],
    plan: ChapterPlan,
    scenes: list[ScenePlan],
    open_hooks: list[str],
    current_arc: str = "",
    style_guide: str = "",
    anti_repetition_notes: tuple[str, ...] = (),
    memory_brief: str = "",
    memories: list[MemorySnippet] | None = None,
    forbidden_knowledge: dict[str, list[str]] | None = None,
    previous_chapter_summary: str = "",
    language: str = "en",
    creative_profile: dict | None = None,
    chapter_word_min: int = 1500,
    chapter_word_max: int = 2500,
    story_state_ledger: str = "",
    creative_contract: dict | None = None,
    current_phase: str = "",
    phase_rules: list[str] | None = None,
) -> WriterContext:
    rules = [rule.description for rule in (world.rules if world else []) if rule.description.strip()]
    if not rules and world is not None and world.summary.strip():
        rules = [world.summary]
    if not rules:
        rules = ["Approved World Bible rules are binding."]
    agent_plan = plan_to_agent(plan, scenes)
    scene_count = max(1, len(agent_plan.scenes))
    target = plan.target_word_count or round((chapter_word_min + chapter_word_max) / 2)
    safe_target = min(target, chapter_word_max - 150)
    safe_target = max(chapter_word_min + 100, safe_target)
    # Scene budgets are a hard assembly contract. Rebalance every scene when
    # an old or partial plan has missing budgets, an unsafe target, or totals
    # that cannot fit the platform range.
    existing = [scene.target_word_count for scene in agent_plan.scenes]
    lower_margin = max(0, (safe_target - chapter_word_min) // scene_count)
    upper_margin = max(0, (chapter_word_max - safe_target) // scene_count)
    if not all(existing) or sum(existing) != safe_target:
        base = safe_target // scene_count
        remainder = safe_target - base * scene_count
        planned_scenes = []
        for index, scene in enumerate(agent_plan.scenes):
            words = base + (1 if index < remainder else 0)
            planned_scenes.append(scene.model_copy(update={
                "target_word_count": words,
                "target_word_min": max(1, words - lower_margin),
                "target_word_max": words + upper_margin,
            }))
        agent_plan = agent_plan.model_copy(update={
            "target_word_count": safe_target,
            "target_word_min": chapter_word_min,
            "target_word_max": chapter_word_max,
            "scenes": planned_scenes,
        })
    else:
        agent_plan = agent_plan.model_copy(update={
            "target_word_count": safe_target,
            "target_word_min": chapter_word_min,
            "target_word_max": chapter_word_max,
            "scenes": [
                scene.model_copy(update={
                    "target_word_min": max(1, scene.target_word_count - lower_margin),
                    "target_word_max": scene.target_word_count + upper_margin,
                })
                for scene in agent_plan.scenes
            ],
        })
    writer_profile = _writer_creative_profile(creative_profile)
    return WriterContext(
        story_bible=story_bible_to_architect(bible),
        world_rules=rules,
        characters=[character_to_agent(item) for item in characters],
        chapter_plan=agent_plan,
        open_hooks=open_hooks,
        constraints=["Do not invent characters absent from context."],
        current_arc=current_arc,
        style_guide=style_guide,
        anti_repetition_notes=anti_repetition_notes,
        memory_brief=memory_brief,
        memories=memories or [],
        forbidden_knowledge=forbidden_knowledge or {},
        previous_chapter_summary=previous_chapter_summary,
        language=language,
        creative_profile=writer_profile,
        chapter_word_min=chapter_word_min,
        chapter_word_max=chapter_word_max,
        novel_constitution=writer_profile.get("novel_constitution", {}),
        environment_bible=writer_profile.get("environment_bible", {}),
        relationship_ledger=writer_profile.get("relationship_ledger", []),
        story_state_ledger=story_state_ledger,
        creative_contract=creative_contract or {},
        current_phase=current_phase,
        phase_rules=tuple(phase_rules or []),
    )
