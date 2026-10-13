from novel_engine.agents.base import AgentResult, BaseAgent
from novel_engine.agents.contracts import WriterContext, WriterInput, WriterOutput
from novel_engine.domain.errors import InvalidStateError
from novel_engine.memory.knowledge import check_prose_for_pov


class WriterAgent(BaseAgent[WriterInput, WriterOutput]):
    name = "writer"
    prompt_file = "agents/writer.yaml"
    input_model = WriterInput
    output_model = WriterOutput

    async def run(self, payload: WriterInput) -> AgentResult[WriterOutput]:
        context = payload.context
        if not context.characters:
            raise InvalidStateError(
                "请先在「角色」页创建至少一个角色后再生成章节（WriterAgent requires characters）"
            )
        if not context.world_rules:
            raise InvalidStateError(
                "请先在「世界观」页完善世界规则后再生成章节（WriterAgent requires world rules）"
            )
        if not context.chapter_plan.scenes:
            raise InvalidStateError(
                "请先为本章添加至少一个场景计划后再生成（WriterAgent requires scene plans）"
            )
        result = await super().run(payload)
        unknown = _unknown_character_names(result.output.used_character_names, context)
        if unknown:
            # Character names are a continuity guard, but an occasional model
            # miss should be repaired automatically.  Keep the original frozen
            # context and ask for a constrained rewrite instead of making the
            # user register every transient alias/title by hand.
            repair_note = _character_repair_note(unknown, context)
            result = await super().run(
                WriterInput(
                    context=context,
                    human_notes=(
                        f"{payload.human_notes}\n\n{repair_note}"
                        if payload.human_notes
                        else repair_note
                    ),
                )
            )
            unknown = _unknown_character_names(result.output.used_character_names, context)
            if unknown:
                raise InvalidStateError(
                    "WriterAgent invented characters absent from context after automatic repair: "
                    + ", ".join(unknown)
                )
        forbidden = context.forbidden_knowledge.get(context.chapter_plan.pov, [])
        check_prose_for_pov(result.output.prose, context.chapter_plan.pov, forbidden)
        return result


def _normalise_character_name(name: str) -> str:
    return "".join(name.casefold().split())


def _allowed_character_names(context: WriterContext) -> set[str]:
    allowed: set[str] = set()
    for character in context.characters:
        allowed.add(_normalise_character_name(character.name))
        allowed.update(_normalise_character_name(alias) for alias in character.aliases)
    return {name for name in allowed if name}


def _unknown_character_names(names: list[str], context: WriterContext) -> list[str]:
    allowed = _allowed_character_names(context)
    unknown: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = _normalise_character_name(name)
        if key and key not in allowed and key not in seen:
            unknown.append(name)
            seen.add(key)
    return unknown


def _character_repair_note(unknown: list[str], context: WriterContext) -> str:
    allowed = [
        "/".join(
            [character.name, *character.aliases]
        )
        for character in context.characters
    ]
    return (
        "自动连续性修订：上一版 used_character_names 包含未登记名称："
        + ", ".join(unknown)
        + "。请重新生成本章，禁止新增有名角色；将这些名称映射为下列已有角色的正式名或别名，"
        "无法映射时删除该人物或改成无名背景人物。used_character_names 只能填写已有角色正式名/别名。"
        "已有角色名录："
        + "；".join(allowed)
    )
