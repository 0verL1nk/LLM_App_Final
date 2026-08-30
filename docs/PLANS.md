# 计划政策与活跃索引

计划分三档，按改动规模选择，不强制所有工作都立计划：

1. **小改动**：轻量 ad-hoc 计划——在 PR 描述里写清背景/方案/风险/测试即可，不建文件。
2. **复杂工作**：登记 exec-plan（`docs/exec-plans/active/<slug>.md`）或直接立 openspec
   change（功能与行为变更优先，见 [references/openspec-workflow.md](references/openspec-workflow.md)）。
   exec-plan 与 openspec 并存时，exec-plan 只做状态指针与剩余工作摘要，任务清单以
   openspec 的 `tasks.md` 为准，不复制条目。
3. **技术债**：不单独立计划，统一登记在 [exec-plans/tech-debt-tracker.md](exec-plans/tech-debt-tracker.md)，
   偿还时再升级为 exec-plan 或 openspec change。

生命周期：`active/` 下的计划完成后移入 `completed/`（或改为指向
`openspec/changes/archive/` 的归档条目，见 [exec-plans/completed/README.md](exec-plans/completed/README.md)），
并保留一段"结果与验证"摘要；失败/放弃的计划也移入 `completed/` 并注明结论，防止同一
方案被反复重新发明。

## 当前活跃计划（2026-08-23）

| 计划 | 状态 | 说明 |
|---|---|---|
| [live-agent-task-eval-baseline](exec-plans/active/live-agent-task-eval-baseline.md) | 收尾中 | 指向 openspec change；剩 6.2 提示词迭代重跑、7.6 pass^k 方差量化、7.7 plan 触发。 |
| [eval-progress-frontend](exec-plans/active/eval-progress-frontend.md) | 进行中 | 应用内评测进度前端：后端服务与 API 已就绪，web 页面与 trials/pass^k 展示待建。 |
| [generic-agent-harness](exec-plans/active/generic-agent-harness.md) | 待立项 | 场景 pack + 按角色模型路由 + run 级委派预算；openspec change 待创建。 |

历史计划：`docs/plans/` 与 `docs/plan/`（本地不入库）；评测基线产物在
`docs/plans/baselines/`。新计划从这里开始，不要复活旧目录的编号体系。
