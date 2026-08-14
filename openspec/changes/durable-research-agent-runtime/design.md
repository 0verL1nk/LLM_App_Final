# Design: Durable Research Agent Runtime

## 1. Design principles

1. **Run owns a user command; Task owns work.** 一个用户问题生成一个 Run；主
   Agent、子 Agent、工具调用、计划步骤均有各自可引用的 item/task 身份。
2. **The event log is canonical; projections are rebuildable.** 所有状态变更先追加
   有序事件，再在同一数据库事务更新查询投影。网页从事件 reducer 恢复，不能从
   展示字符串猜状态。
3. **AI decides, runtime guarantees.** 模型决定是否规划或委派；调度器仅执行
   已声明任务的依赖、租约、取消、重试和结果投递。
4. **One user-facing assistant.** 子 Agent 和工具是同一回答中的工作项，不创建第二
   个聊天窗口。低强调状态在消息下方，完整记录在详情面板。
5. **Evidence remains first class.** 子任务只能返回可验证 evidence ID、结构化
   claim 和摘要；Leader 最终引用仍由本轮结果与证据服务校验。

## 1.1 Research-specific differentiation

PaperSage 不应以“能分出三个角色”作为多 Agent 卖点。Codex 优化的是工作区内
代码、命令、补丁和审批；PaperSage 应优化**从论文原文到可核验理解、协作判断和
可追溯写作**的连续链路。

### A. 论文理解：从检索片段到可导航的论证

每个研究任务的基本交付物是 `EvidencePacket`，而不是角色化自然语言。它包含：

```text
research_question
claims[]             # 原子主张；区分 paper fact / cross-paper synthesis / hypothesis
evidence_refs[]      # doc_uid, chunk_id, page, OCR bbox 或外部 URL
confidence            # evidence coverage, not model self-confidence
limitations[]         # 原文未覆盖、冲突、跨页/表格不确定性
open_questions[]      # 下一次检索、读图、公式或人工确认所需问题
```

`EvidencePacket` 使系统能把“解释一篇论文”拆为可并行但可合并的研究动作：
术语与背景、方法与假设、实验与结论、局限与可复现性、以及与项目内其他论文的
异同。每条事实都可回到 PDF/DOCX/PPTX/图片的页码、文本块和坐标预览；没有证据
的内容必须明确标作综合推断或待验证，而不是伪装成论文结论。

下一阶段可以建立由这些 packet 投影出的 `ClaimGraph`：节点是主张、方法、数据集、
指标和术语，边是 `supports`、`contradicts`、`uses`、`extends`。这是论文理解、横向
比较、证据矩阵和 A2UI 的共同输入，且每条边保留 evidence provenance。

### B. 协作：按认识论职责分工，而不是按写作工序分工

角色是受限能力 profile，不是固定流水线。Leader 根据问题选择一个或多个下列
责任：

| 协作责任 | 产出 | 可访问能力 |
|---|---|---|
| 证据研究 | 证据包、覆盖范围、缺口 | 项目检索、原文定位、受控 Web |
| 方法审读 | 假设、方法假设、实验设计和局限 | 原文、公式/表格定位、技能 |
| 交叉核验 | 支持/冲突矩阵、缺失证据、引用问题 | 多个 EvidencePacket、项目资料 |
| 论证编辑 | 大纲、段落草案、主张—证据映射 | 已验证 packet，不直接扩展事实 |

同一责任可以并发多个 Task，例如分别核验不同论文或同一论文的实验与方法。子
Agent 不能只返回 `[结论]` 文本：`claims`、`evidence_refs`、`limitations` 和
`open_questions` 是 Pydantic 校验的结构化输出；自由文本仅作说明。Leader 的合并
器按 evidence ID 去重、保留冲突而非多数投票，并只将通过本轮 scope 校验的引用
交给最终回答。

这让“协作”有实际增益：可定位每个结论由哪个任务、哪段原文支持；失败任务和
未覆盖问题会成为后续任务，而不会消失在长对话中。

### C. 论文写作：生成可审查的论证，而非一次性润色

写作工作流以 `WritingBrief` 和 `DraftRevision` 为中心：

```text
WritingBrief: audience, purpose, target section, claim budget, style constraints
DraftRevision: section/paragraph text, claim_ids, evidence_refs, change rationale,
               unsupported_claims, citation_gaps, review questions
```

写作 Agent 只能把已验证 EvidencePacket 中的事实转成段落；若提出跨文献归纳，
必须把它标为 synthesis，并至少连接相应的多个 packet。审读 Agent 输出的不是
泛泛“建议润色”，而是可定位的：过度主张、证据不足、方法/结果混淆、反例遗漏、
术语不一致和引用缺口。前端可将草案中的 claim span 映射回证据预览，用户能接受、
拒绝或要求重写一个 revision，而不会覆盖原草稿。

### D. 项目记忆：保留研究状态，而非泛化聊天摘要

现有长期记忆应逐步从 generic semantic/episodic/procedural 条目扩展为可审计的
`ResearchArtifact`：研究问题、术语表、已验证结论、争议、阅读进度、写作大纲、
引用偏好和待验证清单。每个 artifact 有来源 task/run/evidence、有效范围和更新
策略。对话摘要只能是索引线索，不能成为无来源事实的唯一依据。

这四项组合是 PaperSage 的独到能力：**原文坐标证据 → 结构化研究交接 → 可审查
论证/草稿 → 跨会话研究记忆**。模型、角色数量或思维链展示本身都不构成壁垒。

## 2. Target model

```text
Project / Session
  └─ ResearchRun (one user command, root thread id)
       ├─ RunItem (append-only projection of visible work)
       │    ├─ assistant_message / reasoning_summary / plan
       │    ├─ tool_call / agent_task / human_request / presentation
       │    └─ terminal result
       ├─ AgentTask (open-kind root or delegated work unit)
       │    ├─ AgentTaskAttempt (lease, worker, retry, outcome)
       │    └─ child AgentTask[]
       └─ AgentRunEvent (ordered source of truth for replay)
```

### 2.1 `agent_tasks`

| Field | Meaning |
|---|---|
| `task_uid` | UUID, stable public-safe task identity |
| `run_uid` | owning run |
| `parent_task_uid` | nullable parent; root task has null |
| `kind` | `leader`, `subagent`, `tool`, `continuation` |
| `agent_role` | nullable configured role, e.g. `researcher` |
| `status` | `queued`, `leased`, `running`, `waiting_children`, `completed`, `failed`, `cancelled`, `expired` |
| `input_json` / `result_json` | validated task input/result; secrets never stored |
| `idempotency_key` | unique within parent/run for duplicate dispatch protection |
| `continuation_epoch` | monotonic parent-resume generation |
| `created_at`, `started_at`, `finished_at`, `cancel_requested_at` | audit timestamps |

### 2.2 `agent_task_attempts`

Each claim produces one attempt with `attempt_uid`, `task_uid`, `worker_id`, lease
expiry, heartbeat, retry number, normalized error category and completion payload.
A worker may only write its own active lease. Expired leases are reclaimable; a late
worker completion is ignored unless its attempt still owns the task.

### 2.3 `run_items` and events

`agent_run_events` remains the ordered log and gains `schema_version`, `item_uid`,
`task_uid` and a discriminated payload. `run_items` stores the latest complete item
for fast session history queries and may be regenerated from the log.

Initial item kinds:

```text
assistant_message, reasoning_summary, plan, tool_call,
agent_task, human_request, presentation, failure
```

Every item uses this lifecycle:

```text
item.created → item.delta* → item.completed | item.failed | item.cancelled
```

`run.started` / `run.completed` remain operational events but are not a user-facing
item. The terminal Run status is only committed after every required root task and
continuation reaches a terminal state.

## 3. Planning model

`Plan` is a single revisioned snapshot per Run with `goal` and `steps[]`. A step has
an explicit ID, title, status (`pending`, `in_progress`, `completed`, `blocked`,
`failed`), optional dependencies, lane and optional `task_uid`.

- `update_plan` replaces the snapshot only at the next explicit revision.
- There is no Todo compatibility adapter or second planning state.
- The runtime, not the UI, marks a linked step `in_progress` when its task starts
  and terminal when the task ends. Unlinked thinking-only steps may be updated only
  by the Leader tool.
- Exactly one step may be `in_progress` per sequential plan lane. Independent steps
  may declare distinct lanes and run concurrently; this is explicit metadata, not
  inferred from timing.

The model is free to omit a plan for simple questions. No heuristic creates a plan.

## 4. Delegation and continuation

### 4.1 Submit

The Leader receives `delegate_task(role, description, input, depends_on, mode)`.
The tool validates the configured role and capabilities, writes the child
`AgentTask`, its `agent_task` RunItem and an outbox record in one transaction,
then returns `{task_uid, status: "queued"}`. Repeated calls with the same
idempotency key return the same task.

Multiple calls may use the same role; identity is always `task_uid`, never role or
description. A role does not receive delegation tools in the first release, so task
trees are bounded to one child level until recursive policy is explicitly designed.

### 4.2 Dispatch

An application `TaskDispatcher` port has a local worker implementation and a future
queue-backed implementation. Both obey the same repository claim/lease contract:

```text
queued → leased → running → completed | failed | cancelled
                         ↘ waiting_children (root only)
```

The local implementation is a supervised process/worker boundary, not a
`ThreadPoolExecutor` or module-global registry. It periodically reclaims expired
leases and records heartbeats. Queue availability is only a delivery optimization;
SQLite task state plus outbox/reconciliation is the recovery authority.

### 4.3 Join and asynchronous continuation

`mode="join"` pauses the root task in `waiting_children` after its current model
checkpoint and waits for declared children. `mode="background"` returns a handle;
the root may complete a preliminary response while a later explicit user request
inspects the result. The first implementation supports only `join` from Leader
prompts; `background` is reserved in the schema and hidden from the model until
notification UX and follow-up semantics are shipped.

When the final required child becomes terminal, the scheduler transactionally:

1. writes its result/failure event and updates linked plan step;
2. creates a `continuation` task with next `continuation_epoch` and an idempotency
   key derived from parent task + completed child set;
3. enqueues that continuation through the outbox.

The continuation invokes the same parent `thread_id` with synthetic **ToolMessage**
containing only validated child `EvidencePacket` output. It does not replay the
original user prompt, create a second user message or reconstruct state from UI
text. A completed epoch cannot be resumed twice.

## 5. API and SSE contract

Existing endpoints remain:

```text
POST /projects/{project_uid}/sessions/{session_uid}/runs
GET  /runs/{run_uid}
GET  /runs/{run_uid}/events?afterSeq=N
```

New endpoints:

```text
POST /runs/{run_uid}/cancel
POST /runs/{run_uid}/retry
GET  /runs/{run_uid}/items?afterSeq=N
GET  /tasks/{task_uid}
POST /tasks/{task_uid}/cancel
POST /tasks/{task_uid}/retry
POST /tasks/{task_uid}/input
```

All mutations require project/session ownership. Cancel is idempotent: it records a
request first, asks active workers to stop at a safe boundary, and eventually emits
the authoritative item/task terminal event. `retry` creates a new attempt; it never
rewrites a failed attempt or duplicate item.

V2 SSE payload example:

```json
{
  "version": 2,
  "sequence": 42,
  "eventType": "item.completed",
  "runId": "run_…",
  "item": {
    "id": "item_…",
    "type": "agent_task",
    "taskId": "task_…",
    "status": "completed",
    "summary": "检索并核验了 6 条资料"
  }
}
```

The server supports V1 readers during migration by adapting V2 items to the current
`plan.updated`, `tool.execution.*` and `agent.*` event names. New web code consumes
V2 first and keeps V1 only behind a compatibility adapter with a removal date.

## 6. User interface model

- Assistant Markdown and display-safe reasoning stream as ordered message parts.
- `ChainOfThought` receives only actual `tool_call` and `agent_task` item summaries.
- `Plan` receives `ResearchPlan`; `Task` receives plan steps; `Tool` receives a
  completed/active tool item. Status text is user-facing and localized.
- The inspector can open an agent-task item to show role, task objective, result,
  evidence count, attempts, packet limitations and failure/retry state. It must not
  expose system prompt, API credentials or raw hidden reasoning.
- Writing views render `DraftRevision` as a proposal with claim-span evidence links;
  accepting a revision creates a new artifact revision instead of overwriting the
  prior text.
- Reopening a session loads snapshot items then replays `afterSeq`; reducer
  de-duplicates by `(run_uid, sequence)` and item id.

## 7. Migration and rollback

1. Add tables and repositories without changing current execution.
2. Dual-write V1 events and V2 item events; compare projections in shadow tests.
3. Route only delegated child work through durable tasks, keeping direct answers on
   the existing path.
4. Enable continuation behind `DURABLE_AGENT_TASKS_ENABLED` for one project/user
   cohort; monitor stuck lease, duplicate continuation and latency metrics.
5. Make V2 canonical, retire V1 derived delegation and legacy DeepAgents task path.

Rollback disables the feature flag for new Runs. Existing V2 Runs remain readable;
workers finish/cancel from the durable tables. No migration drops or mutates original
messages, events, evidence or LangGraph checkpoints.

## 8. Observability and evaluation

Structured logs and metrics include `run_uid`, `task_uid`, `attempt_uid`, parent
task, role, queue/lease delay, model latency, terminal reason and continuation epoch.
Never log full model context, prompts, credentials or unredacted documents.

Required evaluations:

- direct answer with no plan/delegation;
- one delegated retrieval task;
- two same-role concurrent children;
- child failure and parent replanning;
- worker crash/expired lease/reclaim;
- duplicate enqueue and duplicate completion;
- cancel before claim and during work;
- browser disconnect/reconnect during continuation;
- only valid evidence IDs may reach a final citation;
- old V1 session/history remains readable.
- a writing draft with a fabricated or uncovered claim is flagged and cannot acquire
  a false local-document citation.
## Production dispatch topology

`Run` is an interaction and event owner, not an independently dispatched work queue.
Creating a user Run SHALL atomically create one top-level `AgentTask(kind=leader)`
and one `agent_task_outbox` record. API instances only write these records; they do
not become execution owners. Any worker instance leases the leader Task, executes its
Agent turn, heartbeats the attempt, and records the terminal Run event. Subagent and
continuation work use the same Task/Attempt/outbox lifecycle.

This removes the need for a second run-dispatch table. Duplicate transport delivery is
safe because only the task lease owner may execute or complete the attempt. Startup
reconciliation republishes pending outbox records and reclaims expired attempts. The
current local background queue is a development transport only and must be replaced on
the canonical Run path before multi-instance deployment is claimed.
