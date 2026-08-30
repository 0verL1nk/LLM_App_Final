# Live 评测基线（收尾中）

- **事实来源**：[openspec/changes/live-agent-task-eval-baseline/tasks.md](../../../openspec/changes/live-agent-task-eval-baseline/tasks.md)
  （任务清单与勾选状态以它为准，本文件只做指针与摘要，不复制条目）。
- **设计决策**：[design.md](../../../openspec/changes/live-agent-task-eval-baseline/design.md)——
  scenario runner 是校准器、live runner 是质量度量来源、报告必须携带 run_config 溯源。
- **基线产物**：`docs/plans/baselines/`（scenario 19/19 校准 + live 首轮 6/19 + 迭代 1
  失败子集重跑），命令见 `make eval-baseline` / `make eval-live-smoke EVAL_LIMIT=0`。

## 剩余工作

- **6.2 提示词迭代重跑**：Leader 计划/委派触发提示词继续迭代（7.1 已加入触发规则），
  迭代后全量重跑 live 基线对比，不放宽过程契约。
- **7.6 委派触发方差**：同一用例单跑委派 4 次并行、批量跑 0 次——需 pass^k 重复试验
  量化方差（tasks 3.10 升级为必做），并排查域提示「优先 search_document」与
  「多文档应委派」的优先级冲突。
- **7.7 plan 方差**：`plan_passed` 在 3 个 hybrid 用例失败（模型不建计划），与委派不稳定
  同源，随 7.6 一起量化。

## 已完成（供上下文，不再跟踪）

- 契约漂移修复（`task`→`delegate_task`、并行委派真实检测）与 run_config 报告溯源。
- 用例集 12→19，`forbidden_tool_names` 过程契约，逐条核查裁判协议。
- 迭代 1（tasks 7.1–7.5）：计划/委派触发规则、ToolRuntime 注入修复（见
  [../tech-debt-tracker.md](../tech-debt-tracker.md) 与
  [../../references/langchain-gotchas.md](../../references/langchain-gotchas.md)）、评测双层容错、
  SearXNG 显式关闭、失败子集重跑：结果层 52.6%→92%、证据覆盖→100%。
- 6.1 语料修正：真实 Self-Consistency（arXiv 2203.11171）已进入评测语料
  （`tests/fixtures/papers/rag_agentic_reasoning/`）。
- 6.3 `web_overturn_001` 流式崩溃已随迭代 1 消失并转通过（tasks 7.5）。
