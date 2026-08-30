# Design: eval-web-reliability

## D1：Provider 熔断与冷却（进程内，进程重启即重置）

- 每个 provider 实例维护 `consecutive_failures` 与 `cooldown_until`（`time.monotonic()` 基准）。
- 连续 `PROVIDER_CIRCUIT_FAILURE_THRESHOLD = 3` 次失败（任何 ≥400/异常）→ 进入冷却，
  `PROVIDER_CIRCUIT_COOLDOWN_SECONDS = 60`；冷却到期后第一个查询作为半开探测：
  成功清零计数，失败则冷却时间翻倍（上限 `PROVIDER_CIRCUIT_MAX_COOLDOWN_SECONDS = 600`）。
- 熔断期间链上直接跳过该 provider（日志 INFO 一条 `provider cooling down`，不再每次撞墙刷屏）。
- 状态变化必须打日志：进入冷却/恢复各一条，便于事后归因（对应迭代 4 里 115 次 429 刷屏的教训）。
- 熔断是可用性优化不是语义变更：下游 provider 兜底关系保持不变。
- 常量集中命名（AGENTS.md 禁魔法数字），全部可被环境变量覆盖。

## D2：评测 web 冻结快照（回放优先，显式确定性）

- 快照文件：`tests/evals/fixtures/web_snapshots/<fixture_set>.json`，
  结构 `{normalized_query -> provider_payload_text}`（存 `search_web` 的最终字符串输出，
  与 provider 无关，天然格式稳定）。
- 采集命令：CLI `--record-web` 跑批时把每个新查询的实时结果写入快照（带采集日期）；
  刷新用 `--record-web --refresh` 忽略旧快照重新采集。默认跑批 `--web-fixture <name>`
  启用回放；未指定则走实时（现状）。
- 回放语义：查询未命中快照 → **报错该用例并标记 `web_fixture_miss`**，不静默回落实时
  搜索——确定性优先，缺失是维护问题应显式暴露而不是混入噪声。
- 回放模式下 run_config 记录 `web_fixture` 名称与快照校验和，报告可溯源。
- 这直接把 web 用例从"已知漂移层"变成可回归层：两轮跑批间任何 web 用例翻转都是
  代码/提示词造成的，可归因。

## D3：双裁判对照（量化自评偏置，不改变主判分）

- `make eval-judge-comparison EVAL_FIXTURE=... JUDGE_MODEL=<独立模型>`：同一 fixture 跑两遍
  （agent 执行各一遍，judge 分别为主模型/独立模型），产出逐用例 `agree/disagree` 与
  一致率；一致率进报告与 QUALITY_SCORE。
- agent 执行两遍而不是共享轨迹（当前 judge 与执行耦合），成本 2×；两段式评测
  （轨迹落盘→离线判分，live-agent-task-eval-baseline §8.6）落地后降为 1×——本变更不实现
  两段式，只在设计上不阻碍它。

## 风险

- 熔断误伤瞬时抖动：阈值 3 + 半开探测将误伤窗口限制在分钟级；可用性收益（不再连环撞墙）远大于。
- 快照过期导致 web 用例答案陈旧：快照带采集日期，rubric 中"截至日期"类要求以快照日期为基准表述；
  刷新命令显式化这个责任。
- 双裁判成本：仅按需跑，不进常规基线。
