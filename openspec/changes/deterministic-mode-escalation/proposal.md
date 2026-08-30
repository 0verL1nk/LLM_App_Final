## Why

`execution_routing.py` 的 auto 模式用**关键词计数 + 180 字符长度阈值**判定复杂度——这是仓库编码标准明令禁止的"伪智能"：行为看起来在判断，实际是关键词表命中，不可解释、不可维护、与真实任务结构无关（"请比较三篇论文"命中两个 team 关键词才升团队模式，而真正的结构信号——项目里有几篇文档——完全没参与决策）。

评测矩阵（3 模型 × 2 证据档）同时证明：模式遵从是方差主源，意图承载应从 prose/关键词转向 harness 结构（P1 结论）。删除 LLM 路由器时留下的正空位，应由**结构信号**填补，而不是关键词表。

## What Changes

- auto 路由改为纯结构规则：手动指定优先（不变）→ **项目就绪文档数 ≥ 2 → plan_execute（multi_document_scope）**→ 默认 react（bounded_direct_request）。
- 删除关键词表与长度阈值；`route_reason` 保持可审计。
- agent_teams 不再由 auto 指派——团队协作是用户显式选择（构造性最小权限：递归扇出不应被关键词意外触发）。
- 配合已落地的 plan-nudge（工具结果内渐进提示）构成 P1 的完整落地；plan-first 硬门（多文档首轮检索前必须建计划）留待本变更验证数据后决定。

## Capabilities

### New Capabilities

- `execution-mode-routing`：结构化确定性路由（文档规模信号、可审计理由、无关键词魔法）。

## Impact

- 受影响代码：`agent/application/execution_routing.py`（重写规则）、`agent/application/research_workspace.py`（传入 document_count）、`tests/unit/test_execution_routing.py`。
- 风险：依赖关键词升 plan_execute 的用户行为变化——由 nudge 与产品模式选择器承载；route_reason 变更前端展示无需改动（透传字符串）。
