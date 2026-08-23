# 质量门禁与当前评分

快照日期：2026-08-23。本页回答"仓库现在健康吗、差在哪"；规则本体在
[AGENTS.md](../AGENTS.md) §6/§7 与 `scripts/quality_gate.sh`。

## 门禁与当前状态

| 门禁 | 命令 | 当前状态 |
|---|---|---|
| 单元测试 | `uv run --extra dev python -m pytest tests/unit -q` | 通过：377 个 |
| 仓库开发规则 | `uv run --extra dev python scripts/repository_guard.py --check` | 通过（含 500 行上限与超限基线只减不增） |
| Ruff 全仓 | `uv run --extra dev ruff check .` | 通过 |
| openspec 校验 | `make spec-validate`（`openspec validate <slug> --strict`） | 通过 |
| scenario 校准基线 | `make eval-baseline` | 19/19（回归层，必过——校准裁判与评分管线，非模型质量） |
| live 度量基线 | `make eval-live-smoke EVAL_LIMIT=0`（`--repeat 3 --parallel 3` 可选） | 单轮基线：首轮 6/19（31.6%）→ 基线 2 10/19（53%）→ 收官 8/19（42%，结果层 58%）；pass^3=3 方差基线 5/19（26%）——单轮波动在 pass^k 噪声带内，web 类为已知漂移层 |
| 前端 lint/类型/单测 | `make web-lint web-typecheck web-test` | 通过（随 `make check`/`make ci` 执行） |

单套命令入口：`make check`（快速门）与 `make ci`（完整离线 CI 等价）。

## 数字怎么读

- scenario 19/19 只证明裁判与评分管线稳定（答案与工具调用是预写脚本），**不是**模型
  能力分数；live 数字才度量真实系统——两个 runner 的报告都带 `run_config` 溯源
  （见 [agent-evals.md](agent-evals.md) 与
  [exec-plans/active/live-agent-task-eval-baseline.md](exec-plans/active/live-agent-task-eval-baseline.md)）。
- live 首轮与迭代 1 的口径不同（全量 vs 失败子集重跑），对比时先核对 run_config。

## 已知缺口（Gaps）

- ty 类型检查覆盖有限：阻断门禁（core）只查 `api` + `agent/domain` + `agent/tools`
  + `agent/application/contracts.py`，full 门禁也只到 `api` + `agent` 全包；
  `tests/`、`scripts/`、`utils/` 无类型门禁。
- 检索质量无量化指标（无 recall@k / 金标集）——技术债条目 g。
- CI 无文档新鲜度校验（如 db-schema、本页数字可过期）。
- pass^k 重复试验未落地，委派/计划触发方差未量化——技术债条目 h。

## 维护规则

- 改动影响门禁口径或基线数字时更新本页；技术债状态见
  [exec-plans/tech-debt-tracker.md](exec-plans/tech-debt-tracker.md)。
- 本页数字必须可复现：每行都要能用手表中命令重新生成；无法复现的数字删掉。
