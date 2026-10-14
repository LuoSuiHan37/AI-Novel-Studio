# Agent prompt assets

YAML files under `agents/` are the only source of agent prompt text.
Python loads them through `PromptSpec` (version, variables, provider/model override, temperature).
