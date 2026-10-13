from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import CharacterAgentInput, CharacterAgentOutput


class CharacterAgent(BaseAgent[CharacterAgentInput, CharacterAgentOutput]):
    name = "character"
    prompt_file = "agents/character.yaml"
    input_model = CharacterAgentInput
    output_model = CharacterAgentOutput
