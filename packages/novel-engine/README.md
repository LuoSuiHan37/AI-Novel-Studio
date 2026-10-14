# ai-novel-engine

Domain package for **ai-novel-studio**. It currently contains the multi-agent
workflow and the chapter-generation/memory domain pipeline.

```
src/novel_engine/
  agents/      BaseAgent + 11 specialists (no DB writes, no agent-to-agent calls)
  workflows/   AgentWorkflow scheduler + HITL handoff
  services/    persistence-facing domain services
  providers/   LLM adapters
prompts/agents/*.yaml
```

Prompt *text* lives in YAML. Python only loads and renders.
