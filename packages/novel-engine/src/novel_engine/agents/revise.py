from novel_engine.agents.base import AgentResult, BaseAgent
from novel_engine.agents.contracts import ReviseInput, ReviseOutput


class ReviseAgent(BaseAgent[ReviseInput, ReviseOutput]):
    name = "revise"
    prompt_file = "agents/revise.yaml"
    input_model = ReviseInput
    output_model = ReviseOutput
