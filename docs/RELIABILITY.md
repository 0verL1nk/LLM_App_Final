# 可靠性姿态（Durability Posture）

系统在崩溃、重复投递与并发下如何保持正确。架构背景见
[architecture/agent-runtime.md](architecture/agent-runtime.md)；schema 见
[generated/db-schema.md](generated/db-schema.md)。

## 落库与执行权

- **单事务落库**：Run、LEADER 任务与 outbox 记录在同一数据库事务创建——提交即恢复
  点，不存在"Run 存在但任务丢失"的窗口。
- **执行权 = DB 租约**：worker 以 `BEGIN IMMEDIATE` 写事务对任务/attempt 做
  `lease_expires_at` CAS 认领（`agent/application/task_dispatcher.py`、
  `agent/adapters/orm/database.py`）；重复投递与新 attempt 冲突时被拒
  （`lost_lease`），不存在双重执行同一次尝试。
- **join 幂等（epoch）**：子任务完成触发父 continuation 时带 `continuation_epoch`，
  过期 epoch 的 join 被拒——子任务重试不会让父级吃两次结果。

## 崩溃对账

worker 宿主每轮循环（`agent/application/task_worker_host.py::run_once`）依次对账：

1. 回收过期 outbox 租约（`reclaim_expired_task_outbox_claims`）。
2. 回收过期任务租约（`reconcile_expired`）。
3. 补齐丢失的子任务 join（`reconcile_waiting_child_joins`）。
4. 收敛已完成 continuation 的父级（`reconcile_completed_continuation_parents`）。
5. 补写任务完成但产物缺失的 EvidencePacket（`reconcile_evidence_packet_artifacts`）。

continuation 恢复走**同一 checkpoint 线程**：数据库 thread ID 保证 LangGraph 会话语义，
不另起对话历史。

## 传输与重放

- **SSE 游标重放**：事件带持久递增 sequence，客户端断线后带 `afterSeq` 重放，
  服务端不依赖连接存活。
- **steering 输入**：运行中追加输入是 durable 记录，仅在工具边界后投递、模型调用成功
  才确认；未确认投递可重放，最终回答前未消费的输入原子转交后继 Run。

## 模型调用与评测容错

- `ModelRetryMiddleware`：限流/空输出重试 3 次，指数退避 1s 起、2 倍递增、60s 封顶，
  耗尽上抛（`agent/middlewares/builder.py`）。
- 评测 harness 双层容错：turn 执行与裁判调用各重试一次，仍失败则记录错误继续下一
  用例——单点故障不毁整轮基线（`agent/application/evals/`）。

## 已知限制（如实声明）

- 默认 `PAPERSAGE_TASK_TRANSPORT=local`（桌面/开发，2 workers 本地 nudged 执行）；
  多实例部署必须切 `PAPERSAGE_TASK_TRANSPORT=outbox` 并运行受监督 worker——API 进程
  的内存队列永远不是可靠状态。
- 存储 单 SQLite：写串行化依赖 `BEGIN IMMEDIATE` 与 busy_timeout，多写库部署未验证。
- 会话压缩（SummarizationMiddleware）与 provider KV/prompt 缓存的权衡未做缓存工程，
  长会话存在重复计费成本。
