from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import WorldAgentInput, WorldAgentOutput


class WorldAgent(BaseAgent[WorldAgentInput, WorldAgentOutput]):
    name = "world"
    prompt_file = "agents/world.yaml"
    input_model = WorldAgentInput
    output_model = WorldAgentOutput
