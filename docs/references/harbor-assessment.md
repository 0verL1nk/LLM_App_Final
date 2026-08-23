# Harbor 框架适配性评估（2026-08-23）

裁决：**Monitor —— 不采用、不试点**。来源：harbor-framework/harbor 官方仓库与文档、
Terminal-Bench 2.0 公告（arXiv 2601.11868）、GitHub Issues 抽查。

## 它是什么

Laude Institute（Terminal-Bench 作者团队）的智能体**评测**框架：Task（指令 + 容器环境
+ 测试脚本）→ Job（`harbor run` 并行跑批）→ Trial 产出 reward 与 ATIF 轨迹。纯
Python 3.12+，Apache-2.0，4.5k stars，0.x 高速迭代（每 1–2 周一版，716 open issues）。

## 为什么不引入

1. **类别错配**：它是"容器内终端任务 + 测试脚本程序化判分"，不是持久化执行引擎——
   没有 exactly-once、租约、崩溃对账；与我们自建的 outbox+lease 层零重叠，也替代不了
   LangGraph checkpointer。
2. **评测模型不匹配**：我们的用例是 rubric 裁判的会话式研究任务（对比论文 / 路由判别 /
   弃答），不是容器内可程序化验证的终端任务；迁移需把 agent+SQLite+本地模型打包进镜像
   并重写裁判为测试脚本，成本远大于收益。
3. **工程摩擦**：Windows 有已知在售 bug（安装失败 #2478、路径反斜杠 #1239、CRLF #1240）；
   引入会形成第二 canonical 评测入口，违反 AGENTS.md §3.11 单一入口约束。

## 重评触发条件（任一满足即重估）

- 要建设**沙箱化程序验证**的评测场景（代码执行类 agent 能力）；
- 启动 RL/SFT post-training 需要 rollout 生成管线；
- 出于对标需要跑 Terminal-Bench 2.0 等标准基准。

注：本机 Docker Desktop 可用（2026-08-23 确认），环境侧门槛已不存在；届时以独立
dev 工具形式试用，不与 `agent/application/evals/` canonical 入口耦合。
