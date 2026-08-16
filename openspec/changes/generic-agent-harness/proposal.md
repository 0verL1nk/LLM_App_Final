# Generic Agent Harness(通用执行层 + 场景实例化)

## Why

`durable-research-agent-runtime` 已把运行时核心(AgentTask/Attempt、事件日志、租约、
outbox、continuation)建成场景无关的通用层,但产品语义仍散在代码里:三个角色
定义、research 措辞(`first-level research delegation`)、自由文本交接格式
(`[结论][证据][待验证点]`)都硬在 runtime 模块中,新增场景必须改代码。

2026-08 的 multi-agent 调研显示,前沿 harness(DeerFlow 2.0、Claude Agent SDK、
OpenAI Agents SDK)的共识是"通用 harness + 数据式实例化":角色、提示词、skills
以文件承载,harness 只做可验证的执行保证。harness 里编码的假设会随模型进步
过期,场景语义放在可替换的数据层才不会被焊死。

同时,调研暴露的三个工程缺口正好落在通用层,应随本变更一并修复:

1. 委派任务规格贫瘠(只有 role + description)——MAST 实测最大失败类
   (specification & system design 41.77%);
2. 无 run 级委派预算——multi-agent 约 15× token 成本红线,Anthropic 官方
   自述的早期失败模式即"简单查询 spawn 一堆 subagent";
3. 按角色模型路由已定义未接线——"强 Leader + 便宜 worker"是 15× 成本下
   最直接的减负手段。

## What Changes

1. **场景 pack**:执行模式解析为声明式 pack(角色定义、leader 提示词、能力包、
   预算默认值);新增场景只新增 pack 目录,不改 runtime 代码。现有三个角色迁入
   首个 `research` pack,行为保持不变。
2. **分层输出合同**:每个可委派角色声明 `output_contract`,但仅对机器消费面
   强校验(来源引用可解析、runtime 注入的 provenance);叙事字段宽松约束。
   违约不终态:至多一次修复重试后,原始输出包进 `contract_violation` 信封
   (附原因)照常传回,Leader 自行取舍,违约率进基线指标。硬验证后移:pack
   可在 Leader 最终输出注册校验器(research 的"最终引用 ⊆ 本 run 证据"将来
   在此注册)。首个通用合同 `freeform_v1`;research 专属合同(EvidencePacket
   等)由后续变更在 pack 内声明更严 schema 升级。
3. **委派规格增强**:`delegate_task` 输入增加可选 `output_format` 与
   `boundaries` 字段;委派 system prompt 按"目标 / 输出格式 / 边界 / 工具指引"
   清单教学(Anthropic 委派八原则之二);中间件与工具文案去除 research 专用措辞。
4. **Run 级委派预算**:每 run 最大子任务数(pack 默认 + 环境变量覆盖),超额时
   `delegate_task` 返回 `budget_exceeded` 与重规划引导,不创建任务;预算利用率
   进入基线指标。
5. **按角色模型路由**:`agent.md` 已有的 `model` 字段接线到子任务执行;未声明
   继承 Leader 模型;实际使用的模型记录于 attempt,可审计。
6. **边界固化**:架构测试保证 runtime 模块不得 import `agent.scenarios.*` 的
   具体合同(开放 kind 契约不变);场景内容只存在于 pack 目录。

## Non-goals

- 不把 PaperSage 变成对外发布的通用 agent 框架;通用性止步于"场景以数据实例化"。
- 不在本变更实现 research 场景的具体合同(EvidencePacket、WritingBrief、
  ClaimGraph、ResearchArtifact)——由后续 `research-scenario-pack` 变更承接,
  该变更同时吸收 `durable-research-agent-runtime` §7。
- 不改动 durable runtime 核心(任务/租约/outbox/continuation 已完成且已通用)。
- 不引入递归委派、群聊式协作、A2A、sandbox 或任何写操作工具。
- 不新增第二个执行入口、第二套委派状态或新的特性旗标;继续复用
  `DURABLE_AGENT_TASKS_ENABLED`(委派本身默认关闭,合同/预算/路由随其生效)。
- 不在通用层实现结构化合并引擎;合并仍是 Leader 模型在 continuation 中的决策,
  场景级合并语义(如证据去重、冲突保留)归场景 pack。

## Impact

- Backend:`agent/subagent/` → `agent/scenarios/<name>/`(目录迁移,loader 重定向),
  `DurableDelegationMiddleware`、`delegation_service`、子任务执行器、
  `subagent_task_executor`;`agent/domain` 增加合同注册机制。
- Data:无新表;`agent_task_attempts` 记录实际模型,基线指标仓储扩展
  (预算利用率、合同校验失败数)。
- Tests:架构边界测试扩展、合同校验路径、预算路径、模型路由、场景解析、
  同角色并发(合同化)回归。
- Docs:`docs/architecture/durable-runtime-baseline.md`、架构文档、AGENTS.md
  相关条目联动;`durable-research-agent-runtime` tasks §7 添加承接说明。
- Follow-ups:`research-scenario-pack`(吸收 §7)、后续任意新场景 pack。
