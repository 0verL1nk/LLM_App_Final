# AGENTS.md

PaperSage 项目开发规范与工程化约束（团队约定版）

最后更新：2026-08-12

---

## 1. 目标

本规范用于约束后续开发，避免架构继续劣化，确保：

1. 分层清晰
2. 可测试、可维护
3. 变更可回滚
4. 质量门禁可执行

---

## 2. 目录与分层边界

当前主目录职责：

1. `pages/`：Streamlit 页面入口（薄层，仅处理页面交互与编排调用）
2. `ui/`：可复用 UI 组件与页面渲染函数
3. `agent/`：
   - `domain/` 领域模型与契约
   - `application/` 用例编排
   - `adapters/` 外部依赖适配
   - `orchestration/` 调度策略
   - `a2a/` 协作协议/状态机
4. `utils/`：遗留兼容与通用能力（逐步收敛）
5. `tests/`：单元 / 集成 / eval
6. `docs/plan/`：重构与治理计划
7. `web/`：Vite/React/Electron 客户端；`src/pages` 只负责路由级组合，`src/components`
   只负责展示和交互，`src/lib` 承载 API schema、query 与纯客户端状态。
8. `scripts/`：可重复的开发、发布和仓库 guard；不得承载线上业务逻辑。

依赖方向（必须遵守）：

1. `pages/ui -> agent.application -> agent.domain`
2. `agent.application -> agent.adapters`
3. `agent.adapters -> infra/repository`
4. 禁止 `domain` 依赖 `ui/pages`
5. `web` 只能经 HTTP contract 访问后端，禁止导入 Python 业务模块或复制后端状态机。

---

## 3. 强制约束（MUST）

1. 新业务逻辑禁止写入 `utils/utils.py`。
2. 新增数据库访问必须放在 repository/adapter 层，不允许页面直接写 SQL。
3. 页面层禁止直接调用 LLM SDK（如 `OpenAI(...)`），统一走 adapter/service。
4. 不允许在业务代码中使用 `sys.path.insert` 修补导入路径。
5. 任何功能改动必须包含最小测试或现有测试更新。
6. 涉及配置、行为变更必须更新文档（`README.md` 或 `docs/`）。
7. 不允许硬编码 API Key、Token、密钥。
8. 所有新增函数必须有类型注解（至少参数与返回值）。
9. 错误处理禁止静默 `except Exception: pass`。
10. 所有跨层调用要有清晰命名，禁止“万能工具函数”继续扩散。
11. 同一业务用例默认只允许一个 canonical 入口；新增入口必须说明不可替代的语义价值。
12. 新增抽象层若只做参数透传、别名导出或简单包装，默认不允许落地。
13. UI 负责交互、状态展示与渲染；业务逻辑、运行时编排、数据访问不得混入 `ui/`。
14. 新的 runtime 持久化必须使用 SQLAlchemy Core/ORM table expression + Alembic migration；
    不得新增 `sqlite3` repository。现有 SQLite repository 只能减不增，并按可验证事务边界迁移。
15. 所有可调度工作必须使用通用 `AgentTask(kind, task_uid)` 契约；不得新增 research-only
    task type、进程内任务真相或静态 task-kind 白名单。
16. 所有面向用户的 agent 运行状态必须来自 Run/RunItem/Task 的服务端事实；禁止前端 mock
    进度、来源、context 用量或任务队列。

---

## 4. 禁止事项（MUST NOT）

1. 不允许新增“巨型文件”：
   - 任意代码文件不得超过 500 行。
   - 已登记的历史超限文件只能减少，不能增长；新增文件没有豁免。
2. 不允许在 `pages/` 重复初始化逻辑（DB、用户、session_state）。
3. 不允许在 adapter 中仅做无意义透传（直接 `return utils.xxx`）而不定义清晰接口边界。
4. 不允许新增全局可变状态，除非明确封装在 session/context 对象内。
5. 不允许提交与当前任务无关的大规模格式化噪音。
6. 不允许长期保留历史兼容 facade、wrapper、barrel export 作为主链路入口。
7. 不允许为“看起来更整齐”而新增一层无独立语义的封装。
8. 不允许把页面交互代码、组件渲染代码与业务逻辑、agent 编排逻辑写在同一模块中。
9. 不允许以 re-export、参数透传 wrapper 或双实现作为“拆分”；迁移完成后必须删除旧入口。

---

## 5. 代码风格与实践（SHOULD）

1. 单函数建议控制在 60-80 行以内，超出时拆成私有辅助函数。
2. 复杂逻辑优先“先定义输入输出 schema，再实现”。
3. 使用早返回减少嵌套层级。
4. I/O、LLM 调用、DB 调用与纯逻辑分离。
5. 日志采用结构化信息（至少包含关键上下文：`uuid/project_uid/session_uid`）。
6. 命名清晰表达语义，避免 `data/temp/obj`。
7. 优先组合而非继承，优先协议/接口而非硬耦合实现。

---

## 5.1 简洁性原则（Simple Is Better）

默认遵循“simple is better”：

1. 能直接调用就不要新增 wrapper。
2. 能保留一个入口就不要保留多个别名入口。
3. 能放在已有清晰边界内解决，就不要再加新层。
4. 新抽象必须提供明确收益：状态边界、错误边界、领域语义、可测试 contract，至少满足其一。
5. 如果一个模块只是 `import` 后再导出、或 `return 下游函数(...)`，默认应删除或并回原处。
6. UI 层与业务层边界优先于“方便调用”；不要为了少写一个文件把执行逻辑塞进 `ui/`。

评审时必须追问：

1. 这一层比直接调用多提供了什么语义？
2. 如果删掉这层，边界会变差，还是只会变简单？
3. 这是必要复杂度，还是历史兼容/过度设计造成的额外复杂度？

---

## 6. 测试策略

默认策略：

1. 纯逻辑改动：至少补 1 个单元测试。
2. 跨模块编排改动：单元测试 + 至少 1 个集成测试。
3. 修复 bug：必须新增能复现并防回归的测试。

建议命令：

```bash
# 核心质量门禁（必跑）
bash scripts/quality_gate.sh core

# Windows PowerShell 等价命令（不得因 shell 不同跳过门禁）
pwsh -File scripts/quality_gate.ps1 -Mode core

# 仓库开发规则（代码规模、路径 hack 等）
uv run --extra dev python scripts/repository_guard.py --check

# 目标测试
uv run --extra dev python -m pytest tests/unit -q

# 指定模块测试
uv run --extra dev python -m pytest tests/unit/test_turn_engine.py -q
```

---

## 7. 提交与评审规范

PR 描述至少包含：

1. 背景与问题
2. 改动范围（文件列表）
3. 风险点
4. 回滚方式
5. 测试结果（命令 + 结果）

评审检查清单：

1. 是否破坏分层边界
2. 是否引入跨层反向依赖
3. 是否新增重复初始化或重复逻辑
4. 是否补齐测试与文档
5. 是否存在潜在安全泄露
6. 是否新增 raw `sqlite3` 持久化、前端 mock runtime 事实或超过 500 行的代码文件

---

## 7.1 发布与合并规范（Release & Merge）

背景：merge commit 的正文会内嵌 PR 标题，release-please 会把它和分支上的原提交
各记一次，导致 changelog 条目重复；残留的 `release-as` 钉子会让发布 PR 反复提议
已存在的版本号，合并即撞 tag（1.4.3 事故）。以下规范防止复发：

1. **PR 一律 squash merge**（仓库设置已强制 squash-only）。squash 提交标题取
   PR 标题，正文留空；禁止再引入 merge commit / rebase 合并。
2. **PR 标题必须符合 Conventional Commits**（`feat:`/`fix:`/`chore:`/`docs:`
   等）：squash 之后它就是 main 上的提交，也是 changelog 的唯一来源。
3. **版本号只由 release-please 推进**：禁止手动修改 `CHANGELOG.md`、
   `.release-please-manifest.json`、`agent/__init__.py`、`web/package.json`
   中的版本，禁止手动创建或推送 `v*` tag（tag 推送会触发三平台自动打包）。
4. **`release-as` 钉子是临时手段**：仅紧急指定版本号时添加，且必须在对应的
   发布 PR 合并后的下一个 PR 中移除，不允许在配置中过夜残留。
5. **热修流程**：从 `origin/main` 切 `fix/*` 分支 → 补回归测试 → squash merge
   → 等待 Prepare Release 生成 patch 版本发布 PR → 合并发布。
6. **发布 PR 由 Release Train 定时合并**；紧急时可手动合并，但合并前必须核对
   其目标版本号大于已存在的最新 tag。

---

## 8. 架构演进要求（针对当前项目）

1. `utils/utils.py` 只减不增：新能力必须进新模块。
2. 页面初始化统一收敛到 bootstrap helper。
3. `ui/agent_center_page.py` 继续拆分为 controller / view / state。
4. worker 任务导入路径标准化，禁止 `sys.path.insert` 路径 hack。
5. 质量门禁逐步扩围到 `ui/pages/utils`。
6. Runtime repository 统一迁到 `agent/adapters/orm`；schema 只由 Alembic 管理，禁止
   `create_all` 和运行时 DDL 作为生产迁移路径。

详见：

1. `docs/plan/2026-03-08-项目架构治理与重构计划.md`

---

## 9. 安全与配置

1. 仅从环境变量、用户配置或安全存储读取密钥。
2. 日志中禁止打印完整密钥与敏感凭据。
3. 对外部输入（文件、prompt、路径）做基本校验。
4. 涉及文件读写时校验路径合法性，避免越权访问。

---

## 10. Definition of Done（完成标准）

一个任务被视为“完成”，必须同时满足：

1. 功能达成且无已知阻塞 bug
2. 通过对应质量门禁与测试
3. 文档已更新
4. 无新增架构债务（或已在 PR 中明确登记和偿还计划）
5. 评审意见闭环

---

## 11. 快速决策规则

当遇到“快修 vs 工程化”冲突时：

1. 线上故障先止血，但必须在同 PR 或后续紧邻 PR 补工程化修复。
2. 非紧急需求优先按分层规范实现，不接受一次性脚本式堆叠。
3. 无法一次做完的大改动，按“可回滚的小步提交”推进。
