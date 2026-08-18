## 1. 契约漂移修复

- [x] 1.1 fixture：`project_compare_001` / `hybrid_research_001` 的 `required_tool_names` 迁移为 `["delegate_task"]`
- [x] 1.2 scenario runner：合成委派调用改为 `delegate_task` + `role` 参数，委派调用数补齐到 `min_delegation_count`
- [x] 1.3 scoring：`parallel_delegation` 实现真实检测（单条 assistant 消息内 ≥2 个 `delegate_task` 调用），移除硬编码 False
- [x] 1.4 更新 `tests/evals/test_agent_task_eval_fixture.py` 对旧工具名的断言
- [x] 1.5 `tests/unit/test_agent_evals.py` 新增：并行委派通过、跨消息串行委派不通过、旧 `task` 工具名不产生委派事实

## 2. 报告溯源

- [x] 2.1 `build_eval_report` 增加可选 `run_config` 参数并写入报告
- [x] 2.2 两个 runner 传入 run provenance（runner_mode、agent/judge 模型、DDG 回退开关、fixture 路径）

## 3. 研究驱动的用例集与裁判迭代

- [x] 3.1 新增 7 个用例：`project_contradiction_001`、`project_false_premise_001`、`project_abstain_001`、`web_overturn_001`、`routing_discrimination_local_001`、`routing_discrimination_web_001`、`project_delegation_scaling_001`（共 19 例）
- [x] 3.2 新增 `forbidden_tool_names` 过程契约（loader/scoring/feedback/测试）
- [x] 3.3 裁判提示词升级：逐条核查、引文锚定、信息不足显式声明、先推理后结论
- [x] 3.4 live runner 支持 `--judge-model` / `--judge-base-url`，裁判模型写入 run_config
- [x] 3.5 scenario 校准器补齐新用例的罐头答案、实质化证据载荷与带日期的模拟检索结果（引文锚定裁判要求载荷与答案自洽）
- [x] 3.6 效率层诊断：用例诊断新增 `total_tool_calls`（对齐美团四层评测的效率层；latency 已有）
- [ ] 3.7 （后续）数值容差确定性评分用例（CORE-Bench 教训，需新增 grader 类型）
- [ ] 3.8 （后续）投毒语料忠实度用例与来源注入护栏用例（风险层；需可投毒的 fixture 管线）
- [ ] 3.9 （后续）多轮上下文保留用例（需多轮 harness）
- [ ] 3.10 （后续）pass^k 重复试验与 per-case 成功率历史；裁判人工校准集（20–30 条人工标注，人机一致率阈值参考美团图灵实践 ≥90%、人人一致 ≥85%，用 unknown 占比反查 rubric 定义质量）

## 4. 基线执行与文档

- [x] 4.1 重跑 scenario 校准基线（19 用例）并提交至 `docs/plans/baselines/`（`task-completion-eval-baseline-20260816-scenario.json` + HTML 报告）
- [x] 4.2 运行 live 全量基线（19 用例，DDG 回退开启）并提交至 `docs/plans/baselines/`（`task-completion-live-baseline-20260817.json` + HTML；完成率 31.6%，结果层/过程层 52.6%，证据覆盖 89.5%）
- [x] 4.3 更新 `docs/architecture/agent-runtime.md` 评测小节（两种 runner 定位、轮级委派度量局限）与 `Makefile` eval 目标注释（`--limit 0` = 全量）

## 5. 验证

- [x] 5.1 通过目标单测（352+ 全绿：`test_agent_evals`、`test_agent_eval_process_contracts`、`test_eval_report`、`test_agent_task_eval_fixture`、`test_live_smoke_runner`）与 `repository_guard` / `ruff` 检查
- [x] 5.2 openspec 变更校验通过
- [x] 5.3 基线汇总数字记录于 tasks.md 4.1/4.2 与提交说明

## 7. 迭代 1（2026-08-18：提示词触发 + 工具注入修复 + 双层容错）

修复（首轮 live 发现驱动）：

- [x] 7.1 域提示新增「计划与委派」触发规则（多步先建计划；对比≥2篇/并行证据/需独立审阅 → 同轮并行委派），委派中间件提示同步
- [x] 7.2 修复 ToolRuntime 注入失效：`plan_tools.py` / `durable_delegation.py` 的 `from __future__ import annotations` 使注解字符串化、langchain_core 无法识别 `runtime` 注入参数——移除并加注释防回退；`update_plan` 重写为官方 `StructuredTool.from_function` 模式；计划工具改由 PlanMiddleware 提供；新增真实 agent 路径回归测试 `test_agent_tool_runtime_injection.py`。该 bug 同时影响生产 agent_teams 委派
- [x] 7.3 评测 harness 双层容错（turn 执行 + 裁判调用，重试一次→记错误→继续）；`invoke_structured_model` 对损坏 JSON 重试一次
- [x] 7.4 SearXNG 公共池支持显式关闭（`AGENT_SEARXNG_BASE_URLS=none/off/disabled`）
- [x] 7.5 12 用例失败子集重跑（`task-completion-live-iteration1-20260817.json` + HTML）：结果层 52.6%→92%、证据覆盖→100%、`web_overturn_001` 崩溃消失并转通过、4/12 用例转完成

发现（迭代 1 数据）：

- [ ] 7.6 委派触发不稳定：同一用例单跑委派 4 次并行、批量跑委派 0 次——需 pass^k 重复试验量化方差（3.10 升级为必做），并排查域提示「优先 search_document」与「多文档应委派」的优先级冲突
- [ ] 7.7 `plan_passed` 在 3 个 hybrid 用例仍失败（模型不建计划），与委派不稳定同源

## 6. 首轮 live 基线发现（2026-08-17，MiniMax-M3，19 用例）

- 模型在 `project_delegation_scaling_001` 中自行发现语料标注错误：`2205.00445-Self-Consistency.txt` 实为 MRKL Systems 论文（真实 Self-Consistency 编号 2203.11171）。
- `require_plan` + 委派契约的 5 个用例全部失败于过程层：Leader 不建计划、不委派，直接检索作答——下一迭代应针对 Leader 提示词的计划/委派触发策略（而非放宽契约）。
- web 类用例结果层不达标（DDG 检索质量受限）；`web_overturn_001` 两次执行均崩溃（流式无最终状态），已按"执行错误"如实记录。
- 新增难例有效产生区分度：弃答（`project_abstain_001`）、矛盾判定（`project_contradiction_001`）、禁联网判别（`routing_discrimination_local_001`）均通过，验证契约方向正确。

### 后续项

- [ ] 6.1 修正语料：下载真实 Self-Consistency（arXiv 2203.11171）替换误标文件，或改标为 MRKL 并重写引用该编号的用例前提
- [ ] 6.2 Leader 计划/委派触发的提示词迭代后重跑 live 基线对比
- [ ] 6.3 排查 `web_overturn_001` 的流式无最终状态崩溃（turn_runtime 与 MiniMax 流式兼容性）
