from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import ChapterPlannerInput, ChapterPlannerOutput


class ChapterPlannerAgent(BaseAgent[ChapterPlannerInput, ChapterPlannerOutput]):
    name = "chapter_planner"
    prompt_file = "agents/chapter_planner.yaml"
    input_model = ChapterPlannerInput
    output_model = ChapterPlannerOutput
