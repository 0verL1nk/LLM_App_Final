# openspec 工作流

功能与行为变更走 spec-driven 流程。工具：openspec CLI（`openspec validate <slug> --strict`）。

## change 结构

每次变更是一个目录 `openspec/changes/<slug>/`：

| 文件 | 职责 |
|---|---|
| `proposal.md` | Why（现状问题）+ What Changes + 非目标。控制在 ~500 行内，Why 必须基于可观察事实。 |
| `design.md` | 决策记录：每个 Decision 给理由与被否决的备选。是 [../design-docs/index.md](../design-docs/index.md) 的本体来源。 |
| `tasks.md` | 可勾选任务清单，按 1.x/2.x 分节；迭代发现追加新节（参考 `live-agent-task-eval-baseline` 的 §6/§7 命名）。 |
| `specs/<capability>/spec.md` | 规格 **delta**：`ADDED`/`MODIFIED`/`REMOVED` Requirements + Scenario。 |

## delta 格式的两个坑

1. **MODIFIED 必须包含该 Requirement 的全部 scenario**（重写整条），不是只写变化的那
   条——delta 是替换语义，漏写即丢规格。
2. 每条 Requirement 必须有 `#### Purpose:` 与至少一个 `#### Scenario:`，否则 strict
   校验失败。存量 spec 有 11/13 是历史 delta 格式、缺 Purpose/全量 scenario，对 CLI
   不可见——这是已登记技术债
   （[../exec-plans/tech-debt-tracker.md](../exec-plans/tech-debt-tracker.md) 条目 f），
   归档涉及它们时须先补全。

## 生命周期

1. 立项：创建目录与四件套；`openspec validate <slug> --strict` 必须通过
   （`make spec-validate SPEC=<slug>`）。
2. 开发：按 tasks.md 勾选推进；决策变化回写 design.md，不允许只活在提交信息里。
3. 完成：实现合入后执行归档 `openspec archive <slug>`——specs delta 合并进
   `openspec/specs/<capability>/spec.md` 全量规格，change 移入
   `openspec/changes/archive/<slug>/`。
4. 归档后：若 change 有 exec-plan 指针（`docs/exec-plans/active/`），把指针更新到
   archive 路径并在 [../exec-plans/completed/README.md](../exec-plans/completed/README.md)
   登记；相关决策行在 [../design-docs/index.md](../design-docs/index.md) 更新状态。

## 本仓库约定

- 提交不含 `openspec/` 之外私改 `openspec/specs/`（全量规格只能由归档器生成）。
- proposal 的 Why 引用可复现证据（基线数字、trace、报错），不接受"感觉不好"。
- 小改动不立 change（见 [../PLANS.md](../PLANS.md) 分档规则），防止流程税。
