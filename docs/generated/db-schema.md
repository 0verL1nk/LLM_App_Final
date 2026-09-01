# 数据库 Schema（生成物）

> 本文件由 `scripts/generate_db_schema.py` 从 `agent/adapters/orm/models.py` 生成，禁止手改；改表后运行 `make db-schema` 再生成。

覆盖范围：durable 运行时的 SQLAlchemy Core 表（Alembic 管理迁移，见 `docs/architecture/orm-persistence.md`）。遗留 `sqlite3` 层的表（`memory_events`、`memory_items`，见 `agent/memory/repository.py`）不在本表内，其收敛状态见 `docs/exec-plans/tech-debt-tracker.md` 条目 a。

## agent_runs

Run 是一次用户命令的持久载体：状态、请求/解析执行模式与路由理由；(uuid, client_request_id) 唯一约束提供提交幂等。

| 列 | 类型 | 约束 |
|---|---|---|
| run_uid | VARCHAR | PK |
| project_uid | VARCHAR | NOT NULL |
| session_uid | VARCHAR | NOT NULL |
| uuid | VARCHAR | NOT NULL |
| client_request_id | VARCHAR | NOT NULL |
| prompt | TEXT | NOT NULL |
| status | VARCHAR | NOT NULL |
| error_message | TEXT | NOT NULL, default '' |
| requested_mode | VARCHAR | NOT NULL, default 'auto' |
| resolved_mode | VARCHAR | NOT NULL, default 'react' |
| route_reason | VARCHAR | NOT NULL, default 'legacy_default' |
| created_at | VARCHAR | NOT NULL |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：(uuid, client_request_id) 唯一、idx_agent_runs_session(uuid, project_uid, session_uid, created_at)

## context_memory_items

governed 上下文记忆（L2 会话/L3 项目/L4 用户分层）：scope 复合索引按 uuid+project+level 检索，条目带版本与过期时间。

| 列 | 类型 | 约束 |
|---|---|---|
| memory_uid | VARCHAR | PK |
| uuid | VARCHAR | NOT NULL |
| project_uid | VARCHAR | NOT NULL, default '' |
| session_uid | VARCHAR | NOT NULL, default '' |
| memory_level | VARCHAR | NOT NULL |
| memory_type | VARCHAR | NOT NULL |
| title | TEXT | NOT NULL, default '' |
| content | TEXT | NOT NULL |
| source_run_uid | VARCHAR | NOT NULL, default '' |
| version | INTEGER | NOT NULL, default '1' |
| expires_at | VARCHAR | NOT NULL, default '' |
| created_at | VARCHAR | NOT NULL |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：idx_context_memory_scope(uuid, project_uid, memory_level, updated_at)

## session_context_summaries

会话压缩摘要：每会话一行、版本递增，恢复会话时注入上下文骨架。

| 列 | 类型 | 约束 |
|---|---|---|
| session_uid | VARCHAR | PK |
| project_uid | VARCHAR | NOT NULL |
| uuid | VARCHAR | NOT NULL |
| summary | TEXT | NOT NULL |
| source_run_uid | VARCHAR | NOT NULL, default '' |
| version | INTEGER | NOT NULL, default '1' |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：idx_context_summary_scope(uuid, project_uid)

## agent_evidence_clicks

证据引用点击埋点：记录用户实际展开的证据引用（run 关联），为引用有效性信号积累原始数据。

| 列 | 类型 | 约束 |
|---|---|---|
| id | INTEGER | PK |
| run_uid | VARCHAR | FK→agent_runs.run_uid, NOT NULL |
| user_uuid | VARCHAR | NOT NULL |
| project_uid | VARCHAR | NOT NULL |
| evidence_ref | VARCHAR | NOT NULL |
| item_uid | VARCHAR | NOT NULL, default '' |
| created_at | VARCHAR | NOT NULL |

索引/唯一约束：idx_agent_evidence_clicks_run(run_uid, created_at)

## agent_run_events

Run 的有序事件日志（canonical 真相）：(run_uid, sequence) 唯一，页面重放与投影重建都从它恢复。

| 列 | 类型 | 约束 |
|---|---|---|
| id | INTEGER | PK |
| event_uid | VARCHAR | NOT NULL |
| run_uid | VARCHAR | FK→agent_runs.run_uid, NOT NULL |
| sequence | INTEGER | NOT NULL |
| event_type | VARCHAR | NOT NULL |
| timestamp | VARCHAR | NOT NULL |
| payload_json | TEXT | NOT NULL |
| schema_version | INTEGER | NOT NULL, default '1' |
| item_uid | VARCHAR |  |
| task_uid | VARCHAR |  |

索引/唯一约束：(run_uid, sequence) 唯一、(event_uid) 唯一、idx_agent_run_events_sequence(run_uid, sequence)

## agent_run_items

事件的查询投影：assistant 消息与 V2 工作项（agent_task、human_request 等），供页面与检查器直接读取。

| 列 | 类型 | 约束 |
|---|---|---|
| item_uid | VARCHAR | PK |
| run_uid | VARCHAR | FK→agent_runs.run_uid, NOT NULL |
| task_uid | VARCHAR |  |
| item_type | VARCHAR | NOT NULL |
| status | VARCHAR | NOT NULL |
| payload_json | TEXT | NOT NULL |
| created_at | VARCHAR | NOT NULL |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：idx_agent_run_items_run(run_uid, created_at)

## agent_steering_inputs

运行中用户追加输入队列：仅工具边界后投递、模型调用成功才确认，未确认投递可重放。

| 列 | 类型 | 约束 |
|---|---|---|
| input_uid | VARCHAR | PK |
| run_uid | VARCHAR | FK→agent_runs.run_uid, NOT NULL |
| project_uid | VARCHAR | NOT NULL |
| session_uid | VARCHAR | NOT NULL |
| uuid | VARCHAR | NOT NULL |
| client_request_id | VARCHAR | NOT NULL |
| text | VARCHAR | NOT NULL |
| status | VARCHAR | NOT NULL |
| injected_at | VARCHAR |  |
| confirmed_at | VARCHAR |  |
| created_at | VARCHAR | NOT NULL |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：idx_agent_steering_inputs_run(run_uid, status, created_at)、uq_agent_steering_inputs_request(uuid, client_request_id)

## agent_tasks

通用可调度任务（kind 开放注册）：父子关系、状态机、幂等键与 continuation epoch；不绑定 research 语义。

| 列 | 类型 | 约束 |
|---|---|---|
| task_uid | VARCHAR | PK |
| run_uid | VARCHAR | FK→agent_runs.run_uid, NOT NULL |
| parent_task_uid | VARCHAR | FK→agent_tasks.task_uid |
| parent_task_key | VARCHAR | NOT NULL, default '' |
| kind | VARCHAR | NOT NULL |
| agent_role | VARCHAR | NOT NULL, default '' |
| status | VARCHAR | NOT NULL |
| idempotency_key | VARCHAR | NOT NULL |
| continuation_epoch | INTEGER | NOT NULL, default '0' |
| input_json | TEXT | NOT NULL, default '{}' |
| result_json | TEXT | NOT NULL, default '{}' |
| error_message | TEXT | NOT NULL, default '' |
| current_attempt_uid | VARCHAR |  |
| cancel_requested_at | VARCHAR |  |
| created_at | VARCHAR | NOT NULL |
| started_at | VARCHAR |  |
| finished_at | VARCHAR |  |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：(run_uid, parent_task_key, idempotency_key) 唯一、idx_agent_tasks_runnable(status, created_at)、idx_agent_tasks_parent(parent_task_uid, created_at)

## feedback_analysis_tasks

research-feedback-loop 的轮后分析队列（durable 事件+worker，同 memory_events 模式）：每 Run 一行幂等任务，携带判定所需的 citation audit 事实，状态机含租约认领与失败重试。

| 列 | 类型 | 约束 |
|---|---|---|
| task_uid | VARCHAR | PK |
| run_uid | VARCHAR | FK→agent_runs.run_uid, NOT NULL |
| user_uuid | VARCHAR | NOT NULL |
| project_uid | VARCHAR | NOT NULL |
| session_uid | VARCHAR | NOT NULL |
| citation_audit | VARCHAR | NOT NULL, default '' |
| retrieved_evidence_count | INTEGER | NOT NULL, default '0' |
| evidence_doc_uids_json | TEXT | NOT NULL, default '[]' |
| status | VARCHAR | NOT NULL, default 'pending' |
| error_message | TEXT | NOT NULL, default '' |
| created_at | VARCHAR | NOT NULL |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：(run_uid) 唯一、idx_feedback_analysis_status(status, updated_at)

## feedback_events

确定性规则捕获的用户修正信号事件：event_uid 为 sha256(user+run+signal+digest) 幂等键，载荷只存脱敏预览与指纹（不落 prompt 全文），按项目/信号类型/文档桶聚合成发现。

| 列 | 类型 | 约束 |
|---|---|---|
| event_uid | VARCHAR | PK |
| user_uuid | VARCHAR | NOT NULL |
| project_uid | VARCHAR | NOT NULL |
| session_uid | VARCHAR | NOT NULL |
| run_uid | VARCHAR | FK→agent_runs.run_uid, NOT NULL |
| signal_type | VARCHAR | NOT NULL |
| prompt_digest | VARCHAR | NOT NULL |
| doc_uid | VARCHAR | NOT NULL, default '' |
| payload_json | TEXT | NOT NULL |
| created_at | VARCHAR | NOT NULL |

索引/唯一约束：idx_feedback_events_run(run_uid)、idx_feedback_events_bucket(project_uid, signal_type, doc_uid, created_at)

## research_plans

Run 级执行计划快照：revision 比较交换整体替换，不产生计划历史表。

| 列 | 类型 | 约束 |
|---|---|---|
| run_uid | VARCHAR | PK, FK→agent_runs.run_uid |
| revision | INTEGER | NOT NULL |
| goal | TEXT | NOT NULL |
| created_at | VARCHAR | NOT NULL |
| updated_at | VARCHAR | NOT NULL |

## agent_task_attempts

worker 执行尝试：lease_expires_at 租约与 heartbeat 是唯一执行权凭据，attempt 编号唯一约束支撑重试历史。

| 列 | 类型 | 约束 |
|---|---|---|
| attempt_uid | VARCHAR | PK |
| task_uid | VARCHAR | FK→agent_tasks.task_uid, NOT NULL |
| worker_id | VARCHAR | NOT NULL |
| attempt_number | INTEGER | NOT NULL |
| status | VARCHAR | NOT NULL |
| lease_expires_at | VARCHAR | NOT NULL |
| heartbeat_at | VARCHAR | NOT NULL |
| started_at | VARCHAR |  |
| finished_at | VARCHAR |  |
| error_category | VARCHAR | NOT NULL, default '' |
| error_message | TEXT | NOT NULL, default '' |
| result_json | TEXT | NOT NULL, default '{}' |

索引/唯一约束：(task_uid, attempt_number) 唯一、idx_agent_task_attempts_lease(status, lease_expires_at)

## agent_task_outbox

任务事件发件箱：与任务状态同事务写入，available_at/租约状态驱动可靠投递与重复发布拒绝。

| 列 | 类型 | 约束 |
|---|---|---|
| outbox_uid | VARCHAR | PK |
| task_uid | VARCHAR | FK→agent_tasks.task_uid, NOT NULL |
| event_type | VARCHAR | NOT NULL |
| payload_json | TEXT | NOT NULL |
| status | VARCHAR | NOT NULL |
| available_at | VARCHAR | NOT NULL |
| lease_expires_at | VARCHAR |  |
| created_at | VARCHAR | NOT NULL |
| published_at | VARCHAR |  |

索引/唯一约束：idx_agent_task_outbox_pending(status, available_at)

## research_artifacts

任务产物（EvidencePacket、evidence_merge 等）：内容、证据引用与 task 溯源；task_uid 唯一，崩溃后由对账补写。

| 列 | 类型 | 约束 |
|---|---|---|
| artifact_uid | VARCHAR | PK |
| project_uid | VARCHAR | NOT NULL |
| session_uid | VARCHAR | NOT NULL |
| run_uid | VARCHAR | FK→agent_runs.run_uid, NOT NULL |
| task_uid | VARCHAR | FK→agent_tasks.task_uid, NOT NULL |
| artifact_type | VARCHAR | NOT NULL |
| content_json | TEXT | NOT NULL |
| evidence_refs_json | TEXT | NOT NULL, default '[]' |
| created_at | VARCHAR | NOT NULL |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：(task_uid) 唯一、idx_research_artifacts_project(project_uid, session_uid, created_at)

## research_plan_steps

计划步骤：依赖、泳道与任务链接；被链接任务的认领/终态在同一数据库事务内更新步骤状态。

| 列 | 类型 | 约束 |
|---|---|---|
| run_uid | VARCHAR | PK, FK→research_plans.run_uid |
| step_id | VARCHAR | PK |
| title | TEXT | NOT NULL |
| status | VARCHAR | NOT NULL |
| depends_on_json | TEXT | NOT NULL, default '[]' |
| lane | VARCHAR | NOT NULL |
| task_uid | VARCHAR | FK→agent_tasks.task_uid |
| created_at | VARCHAR | NOT NULL |
| updated_at | VARCHAR | NOT NULL |

索引/唯一约束：idx_research_plan_steps_task(task_uid)
