# ai-novel-studio

AI + Human 协作的英文长篇网文生产系统，面向 AlphaNovel、Wattpad、GoodNovel 等平台。第一阶段题材为 Werewolf Romance。

本仓库是长期维护的 Monorepo，**不是**“一句话生成整本书”的玩具系统。重要阶段必须通过自动审核闸门后才能进入下一步；审核结果、阻断原因和版本均需可追溯。

## 当前完成阶段

**STEP 10：Chapter Generation Workflow**

已完成：

- 章节流水线：Load → Bible/Arc/Plan → Memory Retrieval → ContextPackage → Writer/Editor/Continuity → 重复/相关性/长度闸门 → 修订建议（ERROR 不覆盖原稿）→ Revision → 自动审核批准 → Summary/Memory/CharacterState/Timeline/Hooks/Foreshadowing
- NovelPreset / PlatformPreset（AlphaNovel 规则在 YAML，不写死核心引擎）
- Anti-repetition 按频率与近窗判断，不是永久禁词
- 连续 5 章脚本化测试（状态、世界规则、时间线、Hooks、检索、Revision、人工修改不被覆盖）

尚未实现：完整登录、生产 embedding 联调、真实 LLM 五章联跑。

## 环境要求

- Node.js 20+（推荐 22）
- Python 3.12（Docker API 镜像固定 3.12；本机可用 3.11+ 开发）
- Docker Desktop（用于 Postgres/pgvector，也可一键启动全部服务）
- npm

## 如何启动

在仓库根目录：

```bash
copy .env.example .env
```

macOS / Linux 使用 `cp .env.example .env`。

### 仅数据库

```bash
docker compose up db -d
```

默认把容器 5432 映射到本机 **5433**，避免与已有 Postgres 冲突。`.env` 中的 `DATABASE_URL` 已按 5433 配置。

### 后端

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e ../../packages/novel-engine
pip install -e ".[dev]"
alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

从仓库根目录执行测试时使用 `python -m pytest`；这样会同时加载 API 和
`novel-engine` 的源码路径。生产环境必须设置 `.env` 中的 `API_AUTH_TOKEN`；
开发环境仍保留本地调试身份头，但它不具备生产安全性。

Windows PowerShell 也可以直接运行 `./start.ps1`。启动时请使用项目虚拟环境的 Python；全局 `uvicorn` 不会自动发现 `packages/novel-engine/src` 中的 `novel_engine` 包。

健康检查：

- http://localhost:8000/health
- http://localhost:8000/health/db
- http://localhost:8000/docs

### 前端

```bash
cd apps/web
npm install
npm run dev
```

打开 http://localhost:3000

### 全套 Docker

```bash
docker compose up --build
```

- Web: http://localhost:3000
- API: http://localhost:8000
- Postgres: localhost:5433（宿主机 5432 常被占用，故映射到 5433）

## 测试

```bash
cd apps/api
pytest
```

覆盖：

- API `/health` 与 `/health/db`（后者需要 Postgres）
- 核心表：创建项目 / 角色 / 章节 / CharacterState / StoryMemory，以及关系查询
- LLM Provider（httpx mock，不调用真实模型）
- Novel Engine 领域服务（内存仓储）
- Agent Workflow（httpx/JSON mock，不连真实模型）
- Story Memory 检索与写入策略（24 章模拟，不连真实 embedding API）
- Chapter Generation Pipeline（mock LLM，连续 5 章 HITL）

```bash
alembic -c apps/api/alembic.ini upgrade head
python -m pytest
```

前端验证：`cd apps/web && npm run build`，或 `npm run dev` 后走完创建项目 → Story Bible → 角色/世界/情节 → 章节计划 → 编辑器（预览后再 Apply/Save）。

## 仓库结构

```
apps/web                 Next.js
apps/api                 FastAPI
packages/novel-engine    领域引擎骨架
database                 Alembic 与 Postgres init
docs                     架构、许可证登记、ADR
prompts                  Prompt 资产（禁止写进 Python 业务代码）
```

## 原则

1. 只借鉴开源设计思想，不复制源码。
2. 复用第三方源码前必须检查许可证并写入 `docs/licenses/`。
3. Prompt 不得硬编码在 Python 业务代码中。
4. 自动审核驱动为硬约束；任何自动批准都必须建立在可复现的审核结果之上，不能通过修改状态或报告绕过闸门。

## 独立章节审查

章节生成会先执行本地上下文一致性检查，再由主 Continuity Agent 审查。可通过
`REVIEW_PROVIDER` 启用第二个独立审查模型；例如生成使用 DeepSeek、审查使用 OpenAI：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
REVIEW_PROVIDER=openai
REVIEW_MODEL=gpt-4o-mini
OPENAI_API_KEY=...
```

第二审查模型只负责独立检查，不负责改写正文。任一审查模型报告 `ERROR` 时，章节不会自动进入
`reviewed` 状态；异常短的修订稿也不会覆盖原始草稿。
# AI-Novel-Studio
