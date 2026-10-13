from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import ChapterSummaryInput, ChapterSummaryOutput


class ChapterSummaryAgent(BaseAgent[ChapterSummaryInput, ChapterSummaryOutput]):
    name = "chapter_summary"
    prompt_file = "agents/chapter_summary.yaml"
    input_model = ChapterSummaryInput
    output_model = ChapterSummaryOutput
