from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import OutlineInput, OutlineOutput


class OutlineAgent(BaseAgent[OutlineInput, OutlineOutput]):
    name = "outline"
    prompt_file = "agents/outline.yaml"
    input_model = OutlineInput
    output_model = OutlineOutput
