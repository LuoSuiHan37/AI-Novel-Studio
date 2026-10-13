# Architecture

See the STEP 1 design discussion for the full system architecture.

Current implementation stage: **STEP 10 — Chapter Generation Workflow**.

- HTTP adapters live in `apps/api`. They call `NovelEngine` services and `AgentWorkflow`; they do not reimplement novel rules.
- SQLAlchemy Unit of Work maps ORM rows to domain entities.

- Five memory layers (global, character, timeline, chapter, vector) live in `packages/novel-engine/src/novel_engine/memory`.
- Retrieval returns a compact `ContextPackage`; write policy blocks unconfirmed LLM facts from global canon.
- Agents return Pydantic proposals only. `ChapterGenerationPipeline` schedules draft → human approve → memory/timeline/hooks. Platform rules live in YAML presets.
- Agent prompts live in `packages/novel-engine/prompts/agents/`.

- Domain services live in `packages/novel-engine` and do not import FastAPI.
- Persistence adapters belong in `apps/api` (SQLAlchemy UoW not wired yet).
- Human-in-the-loop: `submit_for_review` → `approve(..., confirmed_by=)` → `pipeline.advance`.

- Frontend: `apps/web`
- Backend: `apps/api`
- Novel engine: `packages/novel-engine` (domain enums + LLM providers; no agents yet)
- Prompt assets: `prompts/` (no hardcoded prompt strings in Python)
- Migrations: `database/alembic`

Persistence ORM lives in `apps/api/app/db/models/`. Domain enumerations live in `packages/novel-engine/src/novel_engine/models/enums.py`. LLM HTTP adapters live in `packages/novel-engine/src/novel_engine/providers/`.
