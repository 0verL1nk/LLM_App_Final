# ARCHITECTURE

PaperSage 顶层架构地图。本文件是入口，深入细节看 `docs/architecture/` 下的专项文档。

最后更新：2026-08-23

---

## 系统形态

桌面优先（Electron 打包）的论文研究助手：本地 FastAPI 后端 + Vite/React 前端，
检索栈（OCR/嵌入/重排/向量库）全本地，生成模型走用户自配置的 OpenAI 兼容端点。

```
web/ (React + TanStack Router/Query, zod, shadcn)
   │  HTTP + SSE（契约见 web/src/lib/schemas.ts 与 api/）
   ▼
api/ (FastAPI 装配 + 路由薄层)
   ▼
agent/
   ├─ application/  用例编排（唯一入口层）
   │    turn_engine · research_workspace · task_dispatcher/delivery
   │    leader/subagent_task_executor · evals · memory · rag_ingestion
   ├─ domain/       契约与状态机（不依赖任何上层）
   │    AgentTask/Attempt 状态机 · evidence_merge · trace · plans
   ├─ adapters/     外部依赖（orm/SQLAlchemy+Alembic · lancedb · llm · rag · ocr）
   ├─ middlewares/  LangChain 中间件栈（trace/retry/plan/delegation/summarization…）
   ├─ tools/  capabilities/  profiles/  prompts/  skills/  subagent/  memory/  rag/
   ▼
存储：SQLite（business + LangGraph checkpoints）· LanceDB（向量+全文）· 本地模型缓存
```

## 关键子系统（深入入口）

| 子系统 | 文档 |
|---|---|
| Agent 运行时（turn/run 生命周期、durable 任务层、中间件栈） | `docs/architecture/agent-runtime.md` |
| Web 应用（页面、SSE、状态投影） | `docs/architecture/web-application.md` |
| ORM 持久化（表、迁移纪律） | `docs/architecture/orm-persistence.md` |
| A2UI 生成式界面契约 | `docs/architecture/a2ui.md` |
| 桌面打包/发布/更新 | `docs/architecture/desktop-*.md` |
| 评测体系 | `docs/agent-evals.md`、`openspec/specs/agent-evals/spec.md` |

## 依赖铁律（由 AGENTS.md 约束 + repository_guard 检查）

1. `web →(HTTP)→ api → application → domain`，单向；domain 不反向依赖。
2. 所有调度走通用 `AgentTask(kind, task_uid)` 契约；执行权是 DB 租约 CAS，不是传输层。
3. 每个模型请求至多一条 provider-facing SystemMessage（中间件合并，不插入历史）。
4. 模式 = 冻结的能力/中间件 profile（`agent/profiles.py`），子代理不装配委派中间件。

## 两个主干数据流

1. **文档流**：上传 → SQLite ingestion 队列 → OCR/解析（页码/多边形/置信度）→
   结构感知切分 → fastembed 嵌入 → LanceDB 版本化发布 → manifest 门控可检索。
2. **研究流**：Run 提交（模式解析）→ Leader 任务（租约）→ turn_engine（流式、
   证据收集、`<evidence>` 引用）→ 可并行委派子任务 → join/continuation 汇总 →
   SSE 事件投影到前端（可重放）。
