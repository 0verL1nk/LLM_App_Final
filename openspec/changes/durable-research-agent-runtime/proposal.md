# Durable Research Agent Runtime

## Why

PaperSage 已具备研究型主 Agent、RAG、revisioned `update_plan` 与
DeepAgents `task` 委派；但当前 `Run` 是唯一持久化执行实体。子 Agent 是一次
工具调用中的临时执行，完成信息再从消息、角色和描述反推。这在浏览器重连时可
显示部分历史，却不能可靠地处理同角色并发、取消、进程重启、失败重试、向主
Agent 交付结果或长期观测。

Codex 的可借鉴处不是代码编辑能力，而是将 `Thread / Turn / Item / child thread`
作为可寻址、可恢复的实体，并使用有类型的项生命周期驱动 UI。PaperSage 应保留
项目资料、证据与坐标定位的产品边界，建立相同级别的研究任务运行时。

本变更 supersedes `refactor-multi-agent-system` 中“仅通过 task tool-call/result
派生完整委派状态”的要求；旧 OpenSpec 保持历史记录，不再作为实现依据。

## What Changes

1. 引入持久化 open-kind `AgentTask`、`AgentTaskAttempt` 与 `RunItem` 投影；`Run`
   仍是一轮用户命令的所有者，Task 是可独立调度的工作单元。
2. 以版本化、强类型的 Run item/event 协议替代前端对通用 `eventType + payload`
   的猜测；保留现有 SSE `sequence` 和历史读取兼容层。
3. 使用单一 `update_plan` 快照表达计划和步骤状态；状态由运行时变更，不由 UI
   或字符串推断。
4. 将子 Agent 委派改为任务调度：稳定 `task_uid`、父子关系、幂等键、租约、
   重试与明确终态；同类型子 Agent 可并发存在。
5. 建立持久化 continuation：子任务完成后以已保存的 ToolMessage/结果恢复父
   Agent，不依赖内存线程、全局字典或 `(role, description)` 关联。
6. 提供 Run/Task 的取消、重新尝试、恢复和人工输入接口；UI 只显示真实的研究
   计划、工具、子任务和可展示推理摘要。
7. 增加任务调度、恢复、并发、取消和证据归属的集成/eval 覆盖，并删除旧的
   临时委派派生和历史兼容入口。
8. 将协作的交付物从自由文本升级为“主张—证据—不确定性—后续问题”研究包，
   为论文理解、跨文献比较和证据可追溯写作建立同一数据平面。

## Non-goals

- 不复制 Codex 的 Shell、Git、文件写入 Sandbox 或批准流程；PaperSage 先保持
  只读研究工具。未来若加入外部写操作，必须单独设计权限与批准协议。
- 不因“复杂问题”或关键词自动强制委派。是否委派、委派角色和任务拆分仍由
  Leader 根据上下文决定；运行时只负责可靠执行。
- 不把 A2UI、推理文本或 UI 卡片当作任务状态来源。
- 不恢复 A2A、TeamRuntime、ThreadPoolExecutor 或进程内全局任务表。
- 不在一个 PR 内替换所有模型/向量/OCR 基础设施。
- 不把“researcher / reviewer / writer”三个提示词角色包装成独到多 Agent 能力；
  只有可复核的研究交付物、证据边界和协作闭环才是产品能力。

## Impact

- Backend：`agent/domain`、`agent/application`、SQLite adapters、任务队列、
  `ResearchWorkspaceService`、FastAPI Run routes。
- Runtime：替换 DeepAgents 临时 `task` 生命周期的主链路；保留文件式角色定义和
  受限 capability 组装。
- Web：SSE reducer、会话恢复、研究详情与 AI Elements `Plan`、`Task`、`Tool`、
  `ChainOfThought` 的数据源。
- Data：新增可迁移 SQLite 表，旧 `agent_runs` / `agent_run_events` 继续可读。
- Docs：架构、API、故障恢复与开发者运行手册。
- Product：论文理解的证据包、争议点与概念关系；协作的可验证交接；写作的
  句段级来源归属和审稿式核验。
