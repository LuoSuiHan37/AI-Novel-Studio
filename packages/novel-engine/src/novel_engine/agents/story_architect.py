from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import StoryArchitectInput, StoryArchitectOutput


class StoryArchitectAgent(BaseAgent[StoryArchitectInput, StoryArchitectOutput]):
    name = "story_architect"
    prompt_file = "agents/story_architect.yaml"
    input_model = StoryArchitectInput
    output_model = StoryArchitectOutput
