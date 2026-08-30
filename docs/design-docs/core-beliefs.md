# 核心理念（agent-first 运行原则）

本仓库实际执行的操作原则。每条都有代码锚点，不是愿景陈述；与
[AGENTS.md](../../AGENTS.md) 的强制约束互补——那里讲"必须"，这里讲"为什么这样设计"。
决策目录见 [index.md](index.md)。

## 1. Durable 执行为底座

执行权在数据库，不在传输层。Run、任务与 outbox 记录单事务落库；worker 以
`BEGIN IMMEDIATE` 租约 CAS 认领（`agent/adapters/orm/database.py`、
`agent/application/task_dispatcher.py`），重复投递被租约拒绝；崩溃后由 worker 宿主的
对账循环回收过期租约、补齐丢失 join、清理孤儿 continuation 与缺失产物
（`agent/application/task_worker_host.py`）。任何"进程内队列即真相"的方案都是倒退。

## 2. 受约束多智能体

多智能体是能力受限的委派，不是自由对话群。子代理定义在 `agent/subagent/*/agent.md`，
启动时 fail-fast 校验；每个角色只有最小权限能力清单（researcher：文档+web+技能；
reviewer：文档+技能；writer：仅技能）。子代理不装配委派中间件，构造上不可递归委派；
同一任务身份永远只是 `task_uid`，角色名不参与生命周期关联。

## 3. 证据可追溯

`<evidence>chunk_id|p页码|o偏移</evidence>` 契约贯穿工具返回、域提示
（`agent/prompts/paper_domain.py`）与子代理系统提示。子任务交付的是
`EvidencePacket`（结构化 claim + 可验证 evidence 引用，`agent/domain/agent_task.py`），
且只有通过项目与授权文档过滤的证据才能进入包
（`agent/application/subagent_task_executor.py::_sanitize_result`）。答案只保留实际引用
的证据；没有证据的内容必须显式标注为推断或待验证，不得伪装成论文结论。

## 4. 评测驱动迭代

基线产物进库（`docs/plans/baselines/`），改版必须对比基线而不是凭感觉。scenario runner
校准裁判与评分管线，live runner 度量真实系统，两者报告可区分（见
[openspec/changes/live-agent-task-eval-baseline](../../openspec/changes/live-agent-task-eval-baseline/design.md)）。
首轮 live 暴露的问题（委派不触发、工具注入崩溃）由迭代 1 修复并用失败子集重跑验证——
Bad Case 是下一次迭代的需求来源。

## 5. 提示词与工具清单必须同步

教训：域提示提到 leader 实际没有的工具时，模型会照做并得到调用报错。提示词提到的每个
工具都必须在对应 profile 的能力清单里真实注册（`agent/profiles.py`、
`agent/capabilities/`）；能力按 profile 显式声明，禁止"提示词里有、运行时没有"的漂移。
已知欠账登记在 [../exec-plans/tech-debt-tracker.md](../exec-plans/tech-debt-tracker.md)。

## 6. 数值常量必须命名、禁伪智能

魔法数字、无依据截断与"看起来智能"的猜测行为一律禁止（详见用户编码标准与
AGENTS.md §3/§5）。检索百分比只在有可度量进度时上报；重排失败时如实记录
`rerank_skipped` 而不是编造分数；OCR 报告"已完成/总页数"，没有进度的阶段不发明百分比。

## 7. Simple is better

完整版见 AGENTS.md §5.1。默认直接调用、单一入口、能并入已有边界就不加新层；新抽象
必须给出状态边界、错误边界、领域语义或可测试 contract 之一的明确收益。评审时追问：
"删掉这层，边界会变差还是只会更简单？"

## 8. openspec 流程承载功能变更

功能与行为变更走 `openspec/changes/<slug>/`（proposal/design/tasks/specs），CLI
`openspec validate <slug> --strict` 必须通过；完成后归档进 `archive/`。流程细节见
[../references/openspec-workflow.md](../references/openspec-workflow.md)。

## 9. 所有开发在 worktree 进行

主工作区保留给并行会话与紧急核对；功能开发在独立 git worktree 分支进行，完成后走
squash PR 合并。发布纪律（conventional commits、release-please 独占版本号）见
[../references/release-pipeline.md](../references/release-pipeline.md)。
