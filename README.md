# ai-novel-studio

AI + Human 协作的英文长篇网文生产系统，面向 AlphaNovel、Wattpad、GoodNovel 等平台。第一阶段题材为 Werewolf Romance。

本仓库是长期维护的 Monorepo，**不是**“一句话生成整本书”的玩具系统。重要阶段必须通过自动审核闸门后才能进入下一步；审核结果、阻断原因和版本均需可追溯。

## 当前完成阶段

**STEP 10：Chapter Generation Workflow**

已完成：

- 章节流水线：Load → Bible/Arc/Plan → Memory Retrieval → ContextPackage → Writer/Editor/Continuity → 重复/相关性/长度闸门 → 修订建议（ERROR 不覆盖原稿）→ Revision → 自动审核批准 → Summary/Memory/CharacterState/Timeline/Hooks/Foreshadowing
- 独立审核双闸门：小说进入正文生产前的 Project Review，以及正文生成后的 Chapter Review；结果和 Prompt 版本记录在作品质量中心
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

## 自动连载流水线

章节目录中的“生成下一章”会自动计算下一章序号，生成并批准章节计划，生成正文，执行审核，并在审核未通过时自动重试（默认最多 2 次）。每次自动操作会写入 `automation_tasks`，可通过 `GET /projects/{project_id}/automation/tasks` 查看。

项目自动连载固定每 20 分钟处理一章，每天最多正式发布 4 章；调度器随 API 服务启动运行。系统优先上传本地已有但尚未发布的章节，没有可上传章节时才生成下一章。章节平台发布使用 `POST /projects/{project_id}/chapters/{number}/publish/draft`，平台严格读取作品的 `target_platform` 标记，只创建该平台的一条任务；在接入官方授权适配器前，任务会保持 `not_configured`，不会虚报上传成功。

每个作品需要先通过 `PUT /projects/{project_id}/automation/platform-binding` 绑定目标平台书籍 ID。发布任务会保存本地章节号、平台书籍 ID、平台章节号、平台章节标题和正文指纹；章节号返回不一致、书籍绑定变化或重复任务都会被阻止。

需要异步排队时调用 `POST /projects/{project_id}/automation/enqueue-next`；接口立即返回 `queued`，后台任务会更新为 `running`、`completed`、`needs_human_review` 或 `failed`。

异常记录可通过 `GET /projects/{project_id}/automation/notifications` 查看并用对应的 `/read` 接口标记；平台任务只有进入 `draft_uploaded` 或 `awaiting_confirmation` 后才能通过 `/automation/publish-tasks/{task_id}/confirm` 进入 `confirmed`，不会绕过平台上传结果直接标记为已发布。

自动正式发布可在自动连载一级页面单独开启。开启后，调度器会按作品的目标章节数和 `target_platform` 标记优先上传本地未发布章节，没有可上传章节时再生成下一章、执行独立审核、上传并正式发布；关闭时仍保留“生成后人工确认发布”流程。每个作品和目标平台按北京时间每天最多正式发布 4 章，达到上限后当天停止，次日自动恢复。只有正式发布成功才会消耗额度。

平台发布时统一传递 `use_ai=true` 和 `contains_ai=true`。浏览器适配器会在平台出现“是否使用 AI”“包含 AI”等确认项时选择“是”；如果页面无法确认该选项，任务会失败并保留异常通知，不会伪造发布成功。每个发布任务必须同时匹配本地项目、章节号和平台书籍 ID，并保存平台章节 ID/章节号与正文指纹，防止重复发布或发错作品。

平台适配器采用显式配置：`*_PUBLISHER_ENABLED=true`、`*_PUBLISH_DRAFT_URL`、`*_PUBLISH_URL` 和 `*_PUBLISH_TOKEN`。草稿接口和正式发布接口接收 JSON `{title, chapter_number, content, mode}`，返回 JSON 中应包含 `id`/`chapter_id`，或 `{accepted: true}`。不同平台的官方字段差异应在适配器边界内转换，不要把平台页面地址直接当成 API 地址。

没有开放 API 的平台可使用浏览器/CDP 适配器：配置 `*_BROWSER_ENABLED=true`、`*_CDP_URL`、`*_AUTHOR_URL` 和选择器 JSON。浏览器必须由用户手动登录；系统只复用现有会话，不自动输入密码、处理二维码或绕过验证码。首次接入应先使用草稿模式验证页面选择器，再开启正式发布。

Windows 下若要让后端复用登录会话，需要用远程调试端口启动一个专用 Chrome 实例（不要直接复用日常 Chrome 配置目录）：

```powershell
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$pwd\.chrome-author-session"
```

在这个专用实例中分别登录三个作者中心，并把对应作者中心地址与选择器写入 `.env`。普通已打开的 Chrome 标签页不会自动暴露给后端；应用检测不到 `127.0.0.1:9222` 时会保持平台任务为 `not_configured`，避免误报上传成功。

数据库升级：`alembic upgrade head`。自动化相关迁移包括 `0007_automation_pipeline`、`0008_platform_chapter_mapping`、`0009_auto_publish_quota`、`0010_quota_timestamps` 和 `0011_fixed_automation_interval`。

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

新建作品必须先在作品侧边栏的“独立审核”中完成 Project Review；只有审核结果允许进入正文生产时，流水线才会进入 `drafting`。章节生成时的独立审核沿用同一审查模型配置，并将章节审核摘要写入作品质量记录。
# AI-Novel-Studio
