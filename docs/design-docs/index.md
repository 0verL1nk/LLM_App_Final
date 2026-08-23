# 设计决策目录

所有影响架构、运行时语义或产品边界的决策都登记在此。决策本体优先落在
openspec change 的 `design.md`；本目录是索引，不是正文。理念与取舍标准见
[core-beliefs.md](core-beliefs.md)。

状态语义：

- **生效**：当前代码遵循该决策，是现役事实。
- **实验**：已合入但仍在验证期，或 change 尚处 proposal/design 阶段。
- **历史**：决策已完成使命，链接保留供追溯，不再约束新代码。

## openspec 进行中的决策（design.md 为本体）

| 主题 | 文档位置 | 状态 | 一句话结论 |
|---|---|---|---|
| Durable 研究运行时 | [openspec/changes/durable-research-agent-runtime/design.md](../../openspec/changes/durable-research-agent-runtime/design.md) | 生效 | Run 拥有用户命令、Task 拥有工作；事件日志是 canonical，执行权只在 DB 租约，子任务交付 `EvidencePacket` 而非自然语言。 |
| 多智能体运行时重构 | [openspec/changes/refactor-multi-agent-system/design.md](../../openspec/changes/refactor-multi-agent-system/design.md) | 生效 | `create_agent_session` 是唯一 Agent 构造入口；委派经 `SubAgentMiddleware` 的 `delegate_task` 上下文隔离，委派事实只从真实 tool-call/result 提取。 |
| 移除遗留异步拦截器 | [openspec/changes/remove-legacy-async-interceptor/design.md](../../openspec/changes/remove-legacy-async-interceptor/design.md) | 生效 | 旧 `agent.a2a`/`agent.orchestration` 整体退役，middleware 是唯一现行入口；不保留兼容 facade（完成摘要见 [../exec-plans/completed/README.md](../exec-plans/completed/README.md)）。 |
| Live 评测基线 | [openspec/changes/live-agent-task-eval-baseline/design.md](../../openspec/changes/live-agent-task-eval-baseline/design.md) | 生效 | scenario runner 只校准裁判与评分管线，live runner 才度量真实系统；报告必须携带 `run_config` 溯源，禁止混淆两种数字。 |
| 自然式 A2UI 表现层 | [openspec/changes/natural-a2ui-presentation/design.md](../../openspec/changes/natural-a2ui-presentation/design.md) | 生效 | 模型不调用 UI 工具，只在正文内联 `<ui>` XML 片段，服务端 schema 校验后编译为 A2UI v0.9.1 envelope（详见 [../architecture/a2ui.md](../architecture/a2ui.md)）。 |
| 论文写作工作区 | [openspec/changes/paper-authoring-workspace/proposal.md](../../openspec/changes/paper-authoring-workspace/proposal.md) | 实验 | 写作主画布是可版本化的 LaTeX `PaperDraft` 与编译产物，对话是协作入口而非替代画布。 |
| 通用 Agent Harness | [../exec-plans/active/generic-agent-harness.md](../exec-plans/active/generic-agent-harness.md) | 实验 | 场景 pack + 按角色模型路由 + run 级委派预算，把 PaperSage 运行时泛化为可复用 harness；openspec change 待立项。 |

## 架构决策（docs/architecture/ 为本体）

| 主题 | 文档位置 | 状态 | 一句话结论 |
|---|---|---|---|
| Agent 运行时 | [../architecture/agent-runtime.md](../architecture/agent-runtime.md) | 生效 | canonical 路径 `web -> api -> agent_center -> create_agent_session -> create_agent`；子代理构造上不可递归委派。 |
| ORM 持久化 | [../architecture/orm-persistence.md](../architecture/orm-persistence.md) | 生效 | 运行时仓储只用 SQLAlchemy Core 表达式 + Alembic，schema 只由迁移管理；裸 SQL 仅限登记过的 PRAGMA/BEGIN IMMEDIATE。 |
| Web 应用 | [../architecture/web-application.md](../architecture/web-application.md) | 生效 | 项目优先的信息架构；TanStack Router/Query 管导航与远端数据，zod 在边界校验。 |
| 桌面应用/打包/更新 | [../architecture/desktop-application.md](../architecture/desktop-application.md) 等 | 生效 | Electron 壳 + PyInstaller 后端；OCR/嵌入模型本地打包，GPU 包由 `PAPERSAGE_DESKTOP_GPU` 控制。 |

## 未单独成文的小型决策（就地记录）

| 主题 | 文档位置 | 状态 | 一句话结论 |
|---|---|---|---|
| thinking 开关按 provider 映射 | `agent/llm_provider.py` | 生效 | DashScope 走 `enable_thinking`（显式 False），MiniMax M3 走 `thinking.type=adaptive/disabled`，OpenAI 走 `reasoning_effort`；按归一化 host 判断，不信任 URL 子串。 |
| 应用内评测服务形态 | `agent/application/evals/run_service.py`、`api/eval_routes.py` | 生效 | 评测循环跑在后台线程，绝不进入 API 请求路径；进度用内存注册表 + 轮询快照，报告产物落 `data/evals/`。 |
| 模型重试边界 | `agent/middlewares/builder.py` | 生效 | `ModelRetryMiddleware` 只重试 `RateLimitError`/`EmptyModelOutputError`，3 次指数退避（1s 起、2 倍、60s 封顶），耗尽后上抛，禁止伪成功。 |

## 历史决策

已归档 change 的决策目录见 `openspec/changes/archive/`：trace 迁移 middleware、
checkpointer 压缩、agent-centric 编排、capabilities 收敛为 tools、任务完成评测接入、
leader-teammate 编排升级、ORM 持久化地基。目录名即结论，正文在各 change 内。

维护规则：新决策先写进对应 change 的 `design.md` 并在此加一行；小型决策可只在本表
登记，但必须给出代码锚点。决策被推翻时把状态改为"历史"并在一句话结论里写明继任者。
