from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import HookAgentInput, HookAgentOutput


class HookAgent(BaseAgent[HookAgentInput, HookAgentOutput]):
    name = "hook"
    prompt_file = "agents/hook.yaml"
    input_model = HookAgentInput
    output_model = HookAgentOutput
