# Design: live-agent-task-eval-baseline

## 背景与问题定位

见 proposal。核心判断：现有"基线"是 scenario 剧本回放（`_ScenarioAgent` 返回罐头答案与合成工具调用），唯一真实执行的是 LLM 裁判；工具改名后 fixture、scenario、scoring 三处不一致，且没有机制能发现这类漂移。

## 决策

### D1：两种 runner，两种用途，报告必须可区分

- scenario runner = 裁判与评分管线的**校准器**（答案可控，验证评分逻辑与裁判稳定性）。
- live runner = 真实系统的**质量度量来源**（真实模型、真实检索器、canonical 轮执行路径）。
- 落地：`build_eval_report` 增加可选 `run_config` 字段；两个 runner 均写入
  `runner_mode`（`scenario_calibration` / `live_model`）、agent/judge 模型名、
  web 回退开关、fixture 路径。报告读者不再需要读代码才能判断数字的含金量。

### D2：parallel_delegation 的可测语义 = 同一 assistant 消息内 ≥2 个 `delegate_task` 调用

理由：

1. 轮级可观测：只需要 output_messages，不依赖 run 级任务表；
2. 与 durable 运行时语义一致：同一条消息里的多个 `delegate_task` 调用会被
   `submit_delegated_agent_task`（幂等键 `leader-tool:{tool_call_id}`）登记为多个
   独立持久任务，天然并发执行；
3. 排除"分两轮各委派一个"的伪并行——那在运行时是串行等待。

替代方案否决：从 AgentTask/attempt 时间戳区间重叠推断真实并发——需要 run 级
harness 与任务表访问，属于 `durable-research-agent-runtime` 的范围。

### D3：轮级 live harness 中委派调用会收到 `durable_run_required` 错误，这是接受的

`delegate_task` 需要 `run_uid`/`task_uid` 运行上下文（`durable_delegation.py`），
轮级 harness 不提供。因此 live 委派用例度量的是 **Leader 的委派行为**（是否委派、
是否选择并行扇出、角色是否正确），不是子代理产物质量。Leader 收到错误后应回退
直查并作答——final judge 与证据契约继续约束答案质量。该局限在
`docs/architecture/agent-runtime.md` 评测小节明示。

### D4：web 用例经 DDG 回退运行

`AGENT_WEB_ENABLE_DDG_FALLBACK=1`（`duckduckgo-search` 已在 requirements 固定版本）。
DDG 限流导致的失败按真实结果记录，不做重试掩盖；回退开关写入 run_config。

### D5：不加新 CLI 开关

`--limit 0` 已表示"不设上限"（selection.py 语义），Makefile 注释更新即可，
不新增 `--all` 之类的别名入口（AGENTS.md 单一入口约束）。

## 风险

- DDG 不可用会使 web 类用例失败率上升：保留为真实结果，remediation 反馈会指向
  web 检索；后续可在 run 级评测中接入付费搜索源。
- 裁判与 agent 使用同一模型时的自评偏置：run_config 记录两者模型名，
  后续可用 `--judge-model` 覆盖复跑对照。
