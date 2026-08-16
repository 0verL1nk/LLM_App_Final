# Design: Generic Agent Harness

## 1. Design principles

1. **Harness guarantees, scenario semantics.** 运行时只提供可验证的执行保证
   (合同校验、预算、模型路由、租约/续跑);一切领域语义(角色、提示词、
   交接合同深度、合并规则)以数据存在于场景 pack。判断标准:新增一个场景
   是否需要改任何 `agent/application` 或 `agent/middlewares` 模块——答案必须是"否"。
2. **Contracts travel with the pack.** 合同是 Pydantic 模型,由 pack 清单以
   dotted path 注册;runtime 经注册表解析,绝不静态 import 某个场景的合同类。
   任务 kind 保持开放契约(`AGENTS.md` 约束 15)。
3. **Validate what machines consume; label what they don't.** 合同只对机器
   必须消费的字段(引用可解析、runtime 注入的 provenance)做强校验;叙事
   字段宽松约束。违约可检测、可归类、可观测,但不因此终态——降级为显式
   标记的信封,由 Leader 取舍。
4. **Budgets are harness-level guarantees.** 预算在 `delegate_task` 提交路径上
   强制执行,不依赖模型自觉;超额是可恢复的工具错误,Leader 可据此重规划。
5. **Assumptions expire; data survives.** 对模型行为的假设(何时委派、产出多
   详尽)只允许出现在 pack 的提示词与预算默认值里,不出现在 runtime 分支中。

## 2. Alternatives considered

**A. 抽成独立通用框架包(对外发布)。** 否决:调研显示框架类项目的壁垒正在消失
(原语被 MCP/skills/官方 SDK 收编),PaperSage 是产品不是框架;通用性止步于
自身场景可插拔。

**B. 场景 pack 叠加在现有 durable runtime 上(本设计)。** 运行时核心已场景
无关,只需把角色/提示词/合同/预算下沉为数据层,并补三个通用保证。改动面小、
与 in-flight change 无冲突、立即消掉自由文本传话问题。

**C. 保持 research 专用,另起通用副本平行演进。** 否决:违反"同一用例一个
canonical 入口"(AGENTS.md 约束 11),双实现必然漂移;且调研(DeerFlow 2.0
弃固定管线)已证明该路线会被迫重写。

## 3. Scenario pack model

```text
agent/scenarios/
  research/
    scenario.yaml          # name, execution_mode, leader_profile, budget defaults
    prompts/leader.md      # Leader 约束提示词(自 agent/prompts/leader.py 迁移)
    roles/
      researcher/agent.md  # 现有格式 + output_contract、model 字段生效
      reviewer/agent.md
      writer/agent.md
    contracts.py           # 本场景注册的合同(可为空,引用通用合同)
```

- `scenario.yaml` 关键字段:`execution_mode`(如 `agent_teams`)、
  `leader_profile`、`max_delegated_tasks_per_run`(默认 6)、
  `role_contracts`(role → dotted contract path,可省略则用通用合同)。
- 解析:执行模式 → pack → (角色集, leader 提示词, 预算, 合同表)。pack 校验
  失败(未知合同引用、重复角色名、非法预算值)在 session 构建时快速失败,
  不做静默回退。
- 现有 `agent/subagent/loader.py` 的解析逻辑迁移为 pack loader;`agent.md`
  front-matter 格式不变,新增字段向后可选。
- 环境覆盖:`PAPERSAGE_MAX_DELEGATED_TASKS_PER_RUN` 覆盖所有 pack 的预算值
  (上限保险丝,优先级高于 pack 默认)。

## 4. Output contracts(分层 + 降级)

调研校正(2026-08-15):主流生产系统(Anthropic 研究系统、Claude Code、
Codex)的子 agent 交接是浓缩自然语言 + 事后核验(CitationAgent 模式),不做
产出时的 schema 硬闸;且形状校验不等于内容验证。据此本设计采用分层合同与
降级语义,严格程度由场景 pack 通过声明更严的合同表达,不由 harness 强制。

- 通用最小合同 `freeform_v1`(领域中立,未声明专属合同的角色默认使用):

```text
summary        # 一段话结论(宽松:非空 + 长度上限)
details[]      # 条目:文本 + 可选来源引用;带引用时引用必须可解析
caveats[]      # 局限、未覆盖、待验证(可选)
provenance     # task_uid/role/attempt 上下文(运行时注入,模型不可伪造)
```

- **强校验只覆盖机器消费面**:provenance 由 runtime 注入(不可伪造);
  details 中出现的来源引用必须可解析(已知 evidence ID 形态或合法 URL)。
  summary/details/caveats 的内容形状不做校验。
- **违约降级,不终态**:执行器持久化前做至多一次带校验错误的修复重试;
  仍违约则将原始输出包进 `contract_violation` 信封(附具体违约原因)照常
  持久化并进入 continuation,任务正常完结。Leader 看到显式违约标记后自行
  取舍;违约率进入基线指标,持续偏高的角色修 prompt 或合同。
- continuation ToolMessage 携带合同有效 payload 或违约信封(`packet` 键,
  形状不变);不存在"无标记的自由文本"交接形态。
- **硬验证后移**:pack 可在 Leader 最终输出注册校验器(复用现有输出校验
  中间件挂点,单轮修订上限;修订后仍违规则带可见标记定稿,不静默发布)。
  research 的"最终引用 ⊆ 本 run 证据"规则由 `research-scenario-pack` 在
  该挂点注册,不进通用层。
- research 专属合同(EvidencePacket 等)是 pack 内声明更严 schema 的升级,
  降级信封始终作为其安全网;机制上无需 runtime 改动。

## 5. Delegation specification

- `DelegateTaskInput` 增加可选 `output_format`(期望的产出形态提示)与
  `boundaries`(边界与不做事项),随任务输入持久化,子 agent system prompt
  注入;缺省不阻断(简单角色允许),但委派 system prompt 按"目标 / 输出格式 /
  边界 / 角色合同摘要"清单教学,并在工具结果中回显角色的合同摘要,让 Leader
  知道将收到什么形状的产物。
- `DurableDelegationMiddleware` 与工具描述文案改为场景中立
  ("first-level research delegation" → "first-level delegation")。

## 6. Budgets and model routing

- 预算在 `submit_delegated_agent_task` 同一事务内检查(计数该 run 已存在的
  `kind='subagent'` 任务);超额返回 `{"error": "budget_exceeded", "limit",
  "current", "guidance"}`,不创建任务、不抛异常,Leader 可继续回答或收敛范围。
- 模型路由:子任务执行器按角色定义的 `model` 构建 chat model(复用用户的
  provider/base_url/api_key 配置);未声明用 Leader 模型;实际模型名写入
  attempt。`agent.md` 的 `model` 字段从"已解析未使用"变为生效。
- 基线指标扩展:`delegation_budget_utilization`(每 run 子任务数 / 预算)、
  `contract_violations`(含违约原因分布)、按角色的模型使用分布。

## 7. Architecture boundary(测试固化)

`tests/unit/test_architecture_boundaries.py` 新增断言:

- `agent/application`、`agent/middlewares`、`agent/adapters` 不得 import
  `agent.scenarios.*`(pack loader 除外);
- 合同解析只能经注册表(dotted path),不得出现场景合同的静态 import;
- `agent/subagent/` 目录删除后不得回归(同 legacy team 的处理方式)。

## 8. Migration and rollback

1. 新增 pack loader 与合同注册表,`agent/subagent/` 迁移至
   `agent/scenarios/research/`(单次原子迁移,不留兼容 re-export,符合
   AGENTS.md 禁止长期 facade)。
2. 合同校验、预算、模型路由在 `DURABLE_AGENT_TASKS_ENABLED` 内生效;该旗标
   默认关闭,关闭路径上的行为(直答、工具、plan)不受影响。
3. 旗标关闭即回滚:已持久化任务照常完结/取消,历史 run 可读(与既有回滚语义
   一致)。
4. 与 in-flight change 的关系:`durable-research-agent-runtime` 继续交付
   §2(V2 事件协议)与 §6(web UI);其 §7(research artifacts)移交
   `research-scenario-pack`(在 tasks.md 中已加承接说明)。两个变更无代码
   顺序依赖,可并行;V2 的 `agent_task` item payload 直接携带合同化 packet。

## 9. Evaluation

- 同角色并发 × 合同:两个并发子任务各自通过校验,payload 不错位。
- 合同违约路径:修复重试后仍违约 → `contract_violation` 信封进入
  continuation,任务正常完结,违约计数入指标,兄弟任务不受影响。
- 最终输出校验挂点:注册校验器的 pack 在答案定稿前触发校验;违约触发单轮
  修订,仍违规则带可见标记定稿,不静默发布。
- 预算:第 N+1 次委派返回 `budget_exceeded`,run 不失败,指标记录利用率。
- 模型路由:声明 model 的角色用声明模型;未声明的继承 Leader;attempt 记录。
- 场景解析:新增 fixture pack(两个角色 + 通用合同)零 runtime 改动即可
  委派(本变更的验收性场景)。
- 回归:现有 run path 基线测试全部保持绿色。
