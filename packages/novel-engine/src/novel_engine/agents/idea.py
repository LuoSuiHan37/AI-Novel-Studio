from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import IdeaInput, IdeaOutput


class IdeaAgent(BaseAgent[IdeaInput, IdeaOutput]):
    name = "idea"
    prompt_file = "agents/idea.yaml"
    input_model = IdeaInput
    output_model = IdeaOutput
