# Story Memory

领域实现：`packages/novel-engine/src/novel_engine/memory`。

Postgres / pgvector 列：`apps/api/app/db/models/memory.py`、`chapter_summaries`，迁移 `0004_story_memory`。

## 五层 Memory

1. **Global** — 世界观、主线、核心人物、硬规则。只接受 `confirmed_fact` 或声明了知情人的 `secret`。
2. **Character** — 经历、知道/不知道、当前状态、关系变化。
3. **Timeline** — 顺序、故事内时间、地点、因果（`caused_by_sequence`）。
4. **Chapter** — summary、key_events、new_facts、character_changes、new_secrets、resolved_secrets、unresolved_hooks。
5. **Vector** — 写入时同步嵌入。测试用词法哈希；生产可用 1536 维 pgvector。

## Retrieval

`RetrievalPipeline.retrieve(RetrievalRequest) -> ContextPackage`

输入：ChapterPlan 要点（POV、地点、人物、arc、hooks）。

检索：最近 N 章摘要 + 地点/人物相关章 + 角色切片 + 相关时间线 + 语义 top-k + 未解 hooks + foreshadow 标签。

压缩：token budget，超限先丢语义命中，再丢较旧章节。禁止把全书塞进上下文。

POV 过滤：`secret` 不得进入无知角色的 semantic_hits；`forbidden_knowledge` 单独带给 Writer。

## Write Policy

- LLM 且无 `confirmed_by`：`confirmed_fact` 降为 `tentative_fact`；禁止写 Global canon。
- `confirmed_fact` 必须有 `confirmed_by`。
- `rumor` / `character_belief` 不得进入 Global。
- `secret` 必须声明 `known_by` 或 `unknown_to`。

认识类型：`confirmed_fact` | `tentative_fact` | `character_belief` | `rumor` | `secret`。
