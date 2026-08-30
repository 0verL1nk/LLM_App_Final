## Why

迭代 4 实测（11 失败用例 × 2 试验，`task-completion-live-iteration4-20260823.json`）暴露搜索 provider 层已成为评测与产品的双重瓶颈：

1. **免 key Firecrawl 限额极低**（官方文档只写 "add a key for higher rate limits"，未公布数字；实测 3 并发 × 每问 2-3 查询的突发模式必然触发）：单轮跑批 115 次 `firecrawl status=429`，退避重试也只是把失败推迟。
2. **Wikipedia 403 已修**（通用 UA 违反 Wikimedia 政策 → 换产品 UA 实测 200），但该轮跑批进程载入的是旧代码，403 贯穿全程——修复需要机制保证可观测生效，而不是靠"下次重启"。
3. **每条 web 查询都从链头撞到链尾**：provider 连续失败后没有任何熔断，115 次 429 意味着每次查询都白白重撞 firecrawl 再落到下游，拖慢整轮并放大 DDG 限流。
4. **web 用例因此不可重复**：同一用例在基线间随搜索结果漂移翻转（web_latest/web_overturn 基线 2 通过、方差基线 3 连败），单轮数字含大量 provider 噪声——提示词与 harness 的改进无法被公平归因。
5. 裁判与 agent 同模型，自评偏置未量化（指标效度缺口）。

## What Changes

- **A. Provider 可用性治理**：进程内 provider 熔断——连续 N 次失败后冷却 T 秒（冷却期内跳过该 provider），半开探测恢复；provider 健康度写入检索/工具日志；`FIRECRAWL_API_KEY` 注入即用付费限额（配置面已支持，补文档）。
- **B. 评测 web 冻结快照**：评测模式下 web 用例的 `search_web` 走"查询→结果"快照回放（fixtures 内版本化，按需刷新命令重新采集），跑批可重复、可回归、不受当日限流影响；快照命中失败时显式报错而不是回落实时搜索（保持确定性）。
- **C. 裁判独立性对照**：`--judge-model` 对照跑任务化（同 fixture 双裁判各跑一遍，报告记录两裁判逐用例一致率），量化自评偏置。

## Capabilities

### New Capabilities

- `eval-web-reliability`：provider 熔断与冷却语义、web 冻结快照回放、双裁判一致率。

### Modified Capabilities

- `web-search-providers`：provider 链新增健康度治理（熔断/冷却/恢复），失败计数与冷却状态可观测。
- `agent-evals`：live 评测的 web 用例支持冻结快照模式；报告 run_config 记录 `web_fixture` 溯源；新增裁判一致率字段。

## Impact

- 受影响代码：`agent/tools/web_search.py`（provider 链治理）、`agent/application/evals/`（快照注入点与裁判对照）、`tests/unit/test_web_search_providers.py`、评测 fixtures 目录。
- 文档：`docs/references/eval-frameworks-assessment.md`（冻结快照从 backlog 转实施）、`docs/QUALITY_SCORE.md`（web 层从"已知漂移"转"快照确定性"）。
- 已修复并纳入本变更记录：Wikipedia 合规 UA（`bdbfd03`）、Firecrawl/SDK/中间件三层退避加厚与封顶。
