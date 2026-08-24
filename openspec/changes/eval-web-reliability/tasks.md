## 1. Provider 可用性治理

- [x] 1.1 provider 包装层加熔断：连续失败阈值/冷却/半开探测/指数冷却封顶，常量命名+env 覆盖
- [x] 1.2 状态变化日志（进入冷却/恢复），冷却期内跳过不打刷屏日志
- [x] 1.3 单测：连续失败进入冷却、冷却期跳过、半开成功恢复、半开失败冷却翻倍封顶
- [x] 1.4 `FIRECRAWL_API_KEY` 付费限额路径文档化（.env.example 与 references）

## 2. 评测 web 冻结快照

- [x] 2.1 快照存取层：读/写/校验和，查询规范化（大小写/空白）
- [x] 2.2 CLI：`--web-fixture`（回放模式，未命中报 `web_fixture_miss`）与 `--record-web`（采集/`--refresh` 刷新）
- [x] 2.3 live harness 注入：回放模式下 `search_web` 走快照包装
- [x] 2.4 采集首版快照（v1：118 条查询，checksum 9c5ed702）（当前 19 用例的全量 web 查询）
- [x] 2.5 run_config 记录 web_fixture 溯源；未命中在报告用例级可见
- [x] 2.6 单测：命中回放/未命中显式失败/刷新覆盖

## 3. 裁判独立性对照

- [x] 3.1 双裁判对照流程（`--judge-trajectories` 离线重判 + `scripts/eval_judge_agreement.py` 一致率）（逐用例 agree/disagree、一致率）
- [x] 3.2 Makefile `eval-judge-agreement` 目标；实测：M3 vs DeepSeek-V4-Flash 裁判一致率 79%（15/19，四处分歧全同向：M3 更严）
- [x] 3.3 单测（一致率计算/零重叠不除零）：对照合并逻辑与一致率计算

## 4. 验证与文档

- [x] 4.1 门禁（pytest/ruff/guard/openspec validate）（pytest/ruff/guard/openspec validate）
- [x] 4.2 确定性证明（determinism-a/b 双跑）：检索侧零漂移——两轮 web 查询逐字节一致；4 处翻转全部为模型行为方差（双向对称，2 升 2 降，总完成率同为 8/19），无一归因于检索
- [x] 4.3 QUALITY_SCORE 与 eval-frameworks-assessment 已更新（冻结快照转实施、一致率入评分卡）（web 层语义变更）与 eval-frameworks-assessment（冻结快照转实施）
