from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import ContinuityInput, ContinuityOutput


class ContinuityAgent(BaseAgent[ContinuityInput, ContinuityOutput]):
    name = "continuity"
    prompt_file = "agents/continuity.yaml"
    input_model = ContinuityInput
    output_model = ContinuityOutput
