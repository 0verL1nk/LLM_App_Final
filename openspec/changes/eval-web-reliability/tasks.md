## 1. Provider 可用性治理

- [x] 1.1 provider 包装层加熔断：连续失败阈值/冷却/半开探测/指数冷却封顶，常量命名+env 覆盖
- [x] 1.2 状态变化日志（进入冷却/恢复），冷却期内跳过不打刷屏日志
- [x] 1.3 单测：连续失败进入冷却、冷却期跳过、半开成功恢复、半开失败冷却翻倍封顶
- [x] 1.4 `FIRECRAWL_API_KEY` 付费限额路径文档化（.env.example 与 references）

## 2. 评测 web 冻结快照

- [ ] 2.1 快照存取层：读/写/校验和，查询规范化（大小写/空白）
- [ ] 2.2 CLI：`--web-fixture`（回放模式，未命中报 `web_fixture_miss`）与 `--record-web`（采集/`--refresh` 刷新）
- [ ] 2.3 live harness 注入：回放模式下 `search_web` 走快照包装
- [ ] 2.4 采集首版快照（当前 19 用例的全量 web 查询）
- [ ] 2.5 run_config 记录 web_fixture 溯源；未命中在报告用例级可见
- [ ] 2.6 单测：命中回放/未命中显式失败/刷新覆盖

## 3. 裁判独立性对照

- [ ] 3.1 `eval-judge-comparison` 流程与报告字段（逐用例 agree/disagree、一致率）
- [ ] 3.2 Makefile 目标 + QUALITY_SCORE 记录一次实测一致率
- [ ] 3.3 单测：对照合并逻辑与一致率计算

## 4. 验证与文档

- [ ] 4.1 全量门禁（pytest/ruff/guard/openspec validate）
- [ ] 4.2 快照模式全量 19 用例基线：web 层两轮重跑零翻转（确定性证明）
- [ ] 4.3 更新 QUALITY_SCORE（web 层语义变更）与 eval-frameworks-assessment（冻结快照转实施）
