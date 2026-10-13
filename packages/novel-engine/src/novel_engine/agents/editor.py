from novel_engine.agents.base import BaseAgent
from novel_engine.agents.contracts import EditorInput, EditorOutput


class EditorAgent(BaseAgent[EditorInput, EditorOutput]):
    name = "editor"
    prompt_file = "agents/editor.yaml"
    input_model = EditorInput
    output_model = EditorOutput
