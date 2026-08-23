# 通用 Agent Harness（待立项）

目标：把 PaperSage 的受约束多智能体运行时泛化为可复用的 harness——同一套 durable
执行、委派与证据契约，换一个"场景 pack"就能服务论文研究之外的领域。当前状态：
**openspec change 待创建**；本文件是立项前的范围共识，立项后以
`openspec/changes/generic-agent-harness/{proposal,design,tasks}.md` 为事实来源，本文件
退化为指针。

## 三根支柱

1. **场景 pack**：领域差异收敛为声明式 pack——系统提示（现在是
   `agent/prompts/paper_domain.py`）、能力清单（`agent/capabilities/` 的五个
   `*_pack` 构建器）、子代理角色（`agent/subagent/*/agent.md`）与 profile 组装
   （`agent/profiles.py`）。新场景=新 pack，不改 worker/调度/持久化。
2. **按角色模型路由**：目前所有角色共用用户配置的单一 OpenAI 兼容端点
   （`agent/llm_provider.py`、`agent/application/subagent_task_executor.py::_model_for_user`）。
   目标是允许 leader/researcher/reviewer/writer 各自绑定不同模型与 thinking 配置
   （thinking 的 provider 映射规则已就位：DashScope `enable_thinking`、MiniMax M3
   `thinking.type`、OpenAI `reasoning_effort`）。
3. **run 级委派预算**：当前委派数量只受 Leader 行为约束（评测显示触发方差大，见
   [live-agent-task-eval-baseline.md](live-agent-task-eval-baseline.md) 7.6）。目标是在
   Run 层声明预算（最多子任务数/并发扇出/预估 token 上限），由 durable 运行时在
   `delegate_task` 落库时强制执行——超预算返回确定性错误，模型据此改走直查路径。

## 已就位的地基（不重复建设）

- durable 任务/outbox/租约执行与对账（`agent/application/task_dispatcher.py`、
  `task_worker_host.py`；架构见 [../../architecture/agent-runtime.md](../../architecture/agent-runtime.md)）。
- `AgentTask(kind, task_uid)` 通用任务契约与开放 kind 注册表（worker 按注入的
  `TaskExecutorRegistry` 解析，新增 kind 不改 schema 与 worker 循环）。
- EvidencePacket 证据契约与授权过滤。

## 立项前置

- live 评测基线的委派方差（7.6）先量化，预算上限才有依据，避免拍脑袋常数。
- 与 `refactor-multi-agent-system` 的结论对齐：不回退到固定流水线，pack 是能力声明
  不是工序编排。
