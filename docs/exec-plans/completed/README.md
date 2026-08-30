# 已完成计划

约定：`docs/exec-plans/active/` 的计划完成后移入本目录（保留"结果与验证"摘要），
或改写为一行指针指向 `openspec/changes/archive/<slug>/`。openspec 归档是首选——
完成的功能变更应随 change 归档；只有从未立 openspec change 的工作才在本目录留全文摘要。

迁入时在下方登记表加一行；摘要回答三个问题：做了什么、怎么验证的、留下什么债
（债转登记 [../tech-debt-tracker.md](../tech-debt-tracker.md)）。

## 登记表

| 计划 | 完成时间 | 归档位置 |
|---|---|---|
| remove-legacy-async-interceptor | 2026-03（change 待归档） | `openspec/changes/remove-legacy-async-interceptor/` |
| live-agent-task-eval-baseline（已修部分） | 2026-08-18（迭代 1） | `openspec/changes/live-agent-task-eval-baseline/`（收尾项仍在 active） |

## remove-legacy-async-interceptor

目标：让运行时、测试、设置与文档一致承认 middleware 是唯一现行入口，删除失效的
异步策略拦截模型。结果：

- 移除设置中心"异步策略拦截"开关与阈值（可调但不生效的错误预期）。
- `tests/evals`、`tests/integration` 不再导入已删除的 `agent.a2a.*`、
  `agent.orchestration.*`，测试锚定 application + middleware 主链路。
- README 等现役文档不再把 `policy_engine.intercept()` 叙述为入口。
- 不保留兼容 facade（决策依据见 change 的 design.md：双入口违反 canonical 入口约束）。
- 验证：单测/集成测试迁移后全绿，`repository_guard` 通过。遗留：change 尚未执行
  openspec 归档步骤（见 [../../references/openspec-workflow.md](../../references/openspec-workflow.md)）。

## live-agent-task-eval-baseline（已完成切片）

change 仍在 active（剩余项见 [../active/live-agent-task-eval-baseline.md](../active/live-agent-task-eval-baseline.md)），
以下切片已完结：

- 契约漂移修复：fixture `required_tool_names` 迁移 `delegate_task`；scenario runner
  合成调用同步 `delegate_task`/`role`；`parallel_delegation` 改为真实检测
  （同一 assistant 消息内 ≥2 个 `delegate_task` 调用）。
- 报告溯源：`build_eval_report` 写入 `run_config`（runner 模式、agent/judge 模型、
  DDG 回退开关、fixture 路径）。
- 用例集 12→19 与 `forbidden_tool_names` 禁止性契约；逐条核查裁判协议。
- 迭代 1（2026-08-18）：域提示计划/委派触发规则；`plan_tools.py`/`durable_delegation.py`
  的 `from __future__ import annotations` 导致 ToolRuntime 注入失效的 bug 修复
  （教训沉淀在 [../../references/langchain-gotchas.md](../../references/langchain-gotchas.md)）；
  评测双层容错（turn + 裁判各重试一次）；SearXNG 公共池可显式关闭。
- 验证：scenario 校准 19/19；live 首轮 6/19（31.6%，结果层 52.6%）；迭代 1 失败子集
  重跑结果层 92%、证据覆盖 100%、`web_overturn_001` 崩溃消失并转通过；新增回归测试
  `test_agent_tool_runtime_injection.py`。
