## Why

委派工具由 `task`（参数 `subagent_type`）更名为 `delegate_task`（参数 `role`）后，评测套件出现三处漂移，且从未被基线回归发现：

1. fixture 中 `project_compare_001` / `hybrid_research_001` 仍校验旧工具名 `task`；
2. scenario runner 仍合成 `task` + `subagent_type` 调用，而 scoring 只从 `delegate_task` + `role` 提取委派事实，委派契约在当前代码上永远失败；
3. `scoring.normalize_turn_result` 将 `parallel_delegation` 硬编码为 `False`，`require_parallel_delegation: true` 的用例不存在可通过的路径。

同时，仓库唯一落盘的基线（2026-03-19）由 scenario runner 生成：答案与工具调用均为预写脚本，唯一真实执行的是 LLM 裁判。它只能校准裁判与评分管线，不能度量真实系统；12 个用例从未在真实模型上全量运行，也没有 live 基线产物。

## What Changes

- fixture 两个委派用例的 `required_tool_names` 迁移到 `delegate_task`；scenario runner 的合成调用同步为 `delegate_task` / `role`。
- `parallel_delegation` 从硬编码改为真实检测：同一条 assistant 消息内出现 ≥2 个 `delegate_task` 调用即判定为并行委派。
- 评测报告新增 run provenance（runner 模式、agent/judge 模型、web 检索回退开关、fixture 路径），使 scenario 校准报告与 live 度量报告可被明确区分。
- live runner 以 `--limit 0` 全量运行用例（web 用例经 DDG 回退执行），live 与 scenario 两份基线产物提交进 `docs/plans/baselines/`。

研究驱动的迭代（依据 Anthropic《Demystifying evals for AI agents》2026-01、DeepResearch Bench、CALM 裁判偏差研究、agentevals 实践、美团图灵《Agent 评测漫谈》2026-08）：

- 用例集从 12 扩到 19：新增跨论文矛盾判定、虚假前提纠错、语料未覆盖弃答、带日期的时效推翻、同形异路由判别对（语料版/联网版各一）、8 篇全量并行委派扩展，补齐"应发生/不应发生"双向覆盖。
- 新增 `forbidden_tool_names` 过程契约：越界工具使用由确定性代码判失败（平衡用例集，防单向优化）。
- 裁判提示词升级为逐条核查协议：rubric 按编号逐项独立判定、引用答案原文片段锚定、信息不足时显式声明而非猜测、先逐项推理后给结论（对齐美团"Rubric 下钻与二元化"与 CALM 偏差缓解）。
- 用例诊断补效率层信号（`total_tool_calls`、`run_latency_ms`），对齐"结果/过程/效率/风险"四层评测框架。
- live runner 支持 `--judge-model` / `--judge-base-url` 独立裁判模型（避免同模型自评偏置），裁判模型写入 run provenance。
- 后续项登记：数值容差评分、投毒语料忠实度用例、来源注入护栏用例、多轮上下文用例、pass^k 重复试验与裁判人工校准集。

## Capabilities

### Modified Capabilities

- `agent-evals`:
  - Task Completion Scoring：委派契约锚定 canonical `delegate_task`/`role` 契约；并行委派为真实检测，禁止硬编码常量。
  - Eval Reports：报告记录 runner 模式与运行溯源，scenario 校准结果不得被误读为 live 系统质量。
  - 新增 Live Runtime Baseline Execution：live runner 经 canonical 轮执行路径运行真实模型并落盘基线。

## Impact

- 受影响代码：`agent/application/evals/scoring.py`、`agent/application/evals/reporting.py`、`tests/evals/run_agent_task_completion_baseline.py`、`tests/evals/run_agent_task_completion_live_smoke.py`、`tests/evals/fixtures/agent_task_eval_set_v1.jsonl`、`tests/evals/test_agent_task_eval_fixture.py`、`tests/unit/test_agent_evals.py`。
- 文档：`docs/architecture/agent-runtime.md` 评测小节、`Makefile` eval 目标注释。
- 不改变运行时行为；委派在 run 级的完整执行评测（子代理真实跑完并 join）仍由 `durable-research-agent-runtime` 变更承接，本变更只度量 Leader 轮级委派行为。
