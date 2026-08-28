# Design: deterministic-mode-escalation

## D1：路由规则（全部结构信号，零文本猜测）

| 优先级 | 条件 | resolved_mode | reason |
|---|---|---|---|
| 1 | requested ∈ {react, plan_execute, agent_teams} | 用户选择 | user_selected |
| 2 | requested 非法 | react | invalid_override_fallback |
| 3 | document_count ≥ MULTI_DOCUMENT_PLAN_THRESHOLD(=2) | plan_execute | multi_document_scope |
| 4 | 其他 | react | bounded_direct_request |

- `prompt` 保留在签名中仅作审计上下文，不参与判定（删除关键词表即删除伪智能面）。
- `document_count` 由调用方 `prepare_turn_run` 以 `list_ready_project_documents` 计数传入——就绪（可检索）文档才是有效信号，处理中的不算。
- agent_teams 从 auto 候选中移除：递归委派能力只应由显式选择解锁。

## D2：与 plan-nudge 的关系

nudge（已上线）在轮内提示"检索已开始仍无计划"；本变更在 run 提交时就把多文档任务挂到计划必用 profile。两者互补：入口结构化 + 轮内渐进提示。若后续评测数据显示仍不够，再评估 plan-first 硬门（首轮 search_document 直接返回"请先建计划"工具结果），避免一步到位的过度约束。

## D3：迁移与兼容

- `resolve_execution_route` 签名新增 keyword-only `document_count: int = 0`（默认 0 → react，向后兼容现有调用方/测试）。
- 旧关键词行为测试（team/plan 关键词命中）改为断言**不再**触发——防止伪智能回归。
