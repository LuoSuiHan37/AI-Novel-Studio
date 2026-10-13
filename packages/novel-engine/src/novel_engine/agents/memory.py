from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import MemoryAgentInput, MemoryAgentOutput


class MemoryAgent(BaseAgent[MemoryAgentInput, MemoryAgentOutput]):
    name = "memory"
    prompt_file = "agents/memory.yaml"
    input_model = MemoryAgentInput
    output_model = MemoryAgentOutput
