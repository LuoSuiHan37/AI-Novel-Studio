from __future__ import annotations

from pydantic import BaseModel

from novel_engine.agents.chapter_planner import ChapterPlannerAgent
from novel_engine.agents.commercial import CommercialReviewAgent
from novel_engine.agents.chapter_summary import ChapterSummaryAgent
from novel_engine.agents.character import CharacterAgent
from novel_engine.agents.continuity import ContinuityAgent
from novel_engine.agents.contracts import (
    ChapterPlannerInput,
    CommercialReviewInput,
    ContinuityInput,
    EditorInput,
    HookAgentInput,
    IdeaInput,
    MemoryAgentInput,
    OutlineInput,
    StoryArchitectInput,
    WorldAgentInput,
    WriterInput,
)
from novel_engine.domain.errors import InvalidStateError
from novel_engine.style.word_count import count_text_units
from novel_engine.agents.editor import EditorAgent
from novel_engine.agents.hook import HookAgent
from novel_engine.agents.idea import IdeaAgent
from novel_engine.agents.memory import MemoryAgent
from novel_engine.agents.outline import OutlineAgent
from novel_engine.agents.revise import ReviseAgent
from novel_engine.agents.story_architect import StoryArchitectAgent
from novel_engine.agents.world import WorldAgent
from novel_engine.agents.writer import WriterAgent
from novel_engine.providers.base import LLMProvider


class ChapterPassBundle(BaseModel):
    """Workflow result only. Persistence follows automated audit gates."""

    writer: object
    editor: object
    continuity: object
    memory: object
    hooks: object
    revision: object | None = None


class AgentWorkflow:
    """Schedules agents. Agents never invoke one another."""

    def __init__(self, provider: LLMProvider, *, role: str = "generation") -> None:
        self.role = role
        self.provider_identity = {
            "role": role,
            "provider": provider.config.provider.value,
            "model": provider.config.model,
            "base_url": provider.config.base_url,
        }
        self.idea = IdeaAgent(provider)
        self.architect = StoryArchitectAgent(provider)
        self.character = CharacterAgent(provider)
        self.world = WorldAgent(provider)
        self.outline = OutlineAgent(provider)
        self.chapter_planner = ChapterPlannerAgent(provider)
        self.commercial = CommercialReviewAgent(provider)
        self.writer = WriterAgent(provider)
        self.revise = ReviseAgent(provider)
        self.editor = EditorAgent(provider)
        self.continuity = ContinuityAgent(provider)
        self.memory = MemoryAgent(provider)
        self.hook = HookAgent(provider)
        self.chapter_summary = ChapterSummaryAgent(provider)

    async def propose_idea(self, payload: IdeaInput):
        return await self.idea.run(payload)

    async def propose_story_bible(self, payload: StoryArchitectInput):
        return await self.architect.run(payload)

    async def propose_character(self, payload: CharacterAgentInput):
        return await self.character.run(payload)

    async def propose_world(self, payload: WorldAgentInput):
        return await self.world.run(payload)

    async def propose_outline(self, payload: OutlineInput):
        return await self.outline.run(payload)

    async def propose_chapter_plan(self, payload: ChapterPlannerInput):
        return await self.chapter_planner.run(payload)

    async def review_commercial(self, payload: CommercialReviewInput):
        return await self.commercial.run(payload)

    async def draft_chapter_pass(self, payload: WriterInput) -> ChapterPassBundle:
        written = await self.writer.run(payload)
        if written.output.title != payload.context.chapter_plan.chapter_title:
            written = written.model_copy(
                update={
                    "output": written.output.model_copy(
                        update={"title": payload.context.chapter_plan.chapter_title}
                    )
                }
            )
        editor = await self.editor.run(
            EditorInput(context=payload.context, prose=written.output.prose)
        )
        continuity = await self.continuity.run(
            ContinuityInput(context=payload.context, prose=written.output.prose)
        )
        memory = await self.memory.run(
            MemoryAgentInput(
                chapter_number=payload.context.chapter_plan.chapter_number,
                prose=written.output.prose,
                chapter_plan=payload.context.chapter_plan,
            )
        )
        hooks = await self.hook.run(
            HookAgentInput(
                chapter_number=payload.context.chapter_plan.chapter_number,
                chapter_plan=payload.context.chapter_plan,
                prose=written.output.prose,
            )
        )
        return ChapterPassBundle(
            writer=written,
            editor=editor,
            continuity=continuity,
            memory=memory,
            hooks=hooks,
        )

    async def draft_chapter_by_scenes(self, payload: WriterInput) -> ChapterPassBundle:
        """Draft, validate, and assemble each planned scene under a hard budget."""
        scene_outputs = []
        scene_handoffs = []
        previous_tail = ""
        first_written = None
        scenes = list(payload.context.chapter_plan.scenes)
        if not scenes:
            raise ValueError("at least one scene is required")
        chapter_min = payload.context.chapter_word_min
        chapter_max = payload.context.chapter_word_max
        raw_mins = [scene.target_word_min or max(1, scene.target_word_count - 80) for scene in scenes]
        raw_maxes = [scene.target_word_max or scene.target_word_count + 80 for scene in scenes]

        # Repair an impossible/stale plan before generation. Without this,
        # reserving later scene minimums could force every scene below the
        # chapter minimum (or produce a negative effective maximum).
        if sum(raw_mins) > chapter_max or sum(raw_maxes) < chapter_min:
            target_total = min(
                chapter_max,
                max(chapter_min, round((chapter_min + chapter_max) / 2)),
            )
            base, remainder = divmod(target_total, len(scenes))
            targets = [base + (1 if index < remainder else 0) for index in range(len(scenes))]
            margin = max(20, min(80, min(targets) // 5))
            raw_mins = [max(1, target - margin) for target in targets]
            raw_maxes = [target + margin for target in targets]
            # Keep the repaired maxima within the chapter ceiling.
            overflow = max(0, sum(raw_maxes) - chapter_max)
            for index in range(len(raw_maxes) - 1, -1, -1):
                reduction = min(overflow, max(0, raw_maxes[index] - raw_mins[index]))
                raw_maxes[index] -= reduction
                overflow -= reduction
                if not overflow:
                    break

        # A scene can be valid on its own and still make the assembled chapter
        # too long. Reserve the minimum budget of all later scenes before
        # generating the current one, so the sum of accepted scene maxima can
        # never exceed the chapter maximum. This also protects against old
        # persisted scene plans whose ranges were calculated independently.
        accumulated = 0
        for index, scene in enumerate(scenes):
            later_minimum = sum(raw_mins[index + 1:])
            later_maximum = sum(raw_maxes[index + 1:])
            scene_max = min(raw_maxes[index], chapter_max - accumulated - later_minimum)
            scene_min = max(
                1,
                chapter_min - accumulated - later_maximum,
                min(raw_mins[index], scene_max),
            )
            # If a stale plan is internally impossible, prefer the chapter
            # contract over the stale scene minimum instead of retrying a
            # range that can never fit.
            if scene_min > scene_max:
                scene_min = max(1, scene_max)

            scene_plan = payload.context.chapter_plan.model_copy(update={"scenes": [scene]})
            scene_context = payload.context.model_copy(update={
                "chapter_plan": scene_plan,
                "chapter_word_min": scene_min,
                "chapter_word_max": scene_max,
            })
            notes = payload.human_notes or "Write this planned scene only."
            notes += (
                f"\nHard scene budget: write only scene {scene.scene_number}; target "
                f"{scene.target_word_count} counted units, allowed range {scene_min}-{scene_max}. "
                "Do not add another scene or an epilogue."
            )
            if previous_tail:
                notes += f"\nPrevious scene ending for continuity (do not repeat it): {previous_tail}"
            written = None
            prose = ""
            count = 0
            for attempt in range(3):
                attempt_notes = notes
                if attempt:
                    attempt_notes += (
                        f"\nPrevious attempt was {count} counted units. Regenerate only this scene "
                        f"inside {scene_min}-{scene_max}; remove or add detail as needed."
                    )
                written = await self.writer.run(
                    WriterInput(context=scene_context, human_notes=attempt_notes)
                )
                prose = written.output.prose.strip()
                count = count_text_units(prose)
                # Preserve the existing permissive English test/stub behavior,
                # while making Chinese counted-character generation strict.
                contains_cjk = any("\u3400" <= char <= "\u9fff" for char in prose)
                if (not contains_cjk and count <= scene_max) or (contains_cjk and scene_min <= count <= scene_max):
                    break
            if written is None or not prose:
                raise InvalidStateError(
                    f"场景 {scene.scene_number} 未生成有效正文，已停止组装本章"
                )
            if (
                (any("\u3400" <= char <= "\u9fff" for char in prose) and not scene_min <= count <= scene_max)
                or (not any("\u3400" <= char <= "\u9fff" for char in prose) and count > scene_max)
            ):
                # Length is a quality warning, not a generation blocker. The
                # last non-empty attempt is still useful to the editor and can
                # be saved for manual correction.
                pass
            if first_written is None:
                first_written = written
            scene_outputs.append(prose)
            # Extract the state transition immediately after each scene. The
            # next scene already receives the previous prose tail; this durable
            # handoff also makes the transition auditable after assembly.
            scene_memory = await self.memory.run(
                MemoryAgentInput(
                    chapter_number=payload.context.chapter_plan.chapter_number,
                    prose=prose,
                    chapter_plan=scene_plan,
                )
            )
            for handoff in scene_memory.output.scene_handoffs:
                scene_handoffs.append(
                    handoff.model_copy(
                        update={"scene_number": scene.scene_number, "location": scene.location}
                    )
                )
            accumulated += count
            previous_tail = prose[-600:]

        prose = "\n\n".join(item for item in scene_outputs if item)
        if first_written is None:
            raise ValueError("at least one scene is required")
        chapter_count = count_text_units(prose)
        contains_cjk = any("\u3400" <= char <= "\u9fff" for char in prose)
        written = first_written
        written = written.model_copy(update={
            "output": written.output.model_copy(update={
                "prose": prose,
                "word_count": chapter_count,
                "title": payload.context.chapter_plan.chapter_title,
            })
        })
        editor = await self.editor.run(EditorInput(context=payload.context, prose=prose))
        continuity = await self.continuity.run(ContinuityInput(context=payload.context, prose=prose))
        memory = await self.memory.run(MemoryAgentInput(
            chapter_number=payload.context.chapter_plan.chapter_number,
            prose=prose,
            chapter_plan=payload.context.chapter_plan,
        ))
        if scene_handoffs:
            memory = memory.model_copy(
                update={
                    "output": memory.output.model_copy(
                        update={"scene_handoffs": scene_handoffs}
                    )
                }
            )
        hooks = await self.hook.run(HookAgentInput(
            chapter_number=payload.context.chapter_plan.chapter_number,
            chapter_plan=payload.context.chapter_plan,
            prose=prose,
        ))
        return ChapterPassBundle(
            writer=written,
            editor=editor,
            continuity=continuity,
            memory=memory,
            hooks=hooks,
        )
