# 架构设计

```text
pages/ui
  -> agent.application.agent_center
  -> create_agent_session
  -> LangChain create_agent
       + SubAgentMiddleware(task)
       + Todo/Plan/Trace middleware
       + bounded domain tools
```

Leader 负责拆解、并行发出独立 `task` 调用并综合结果。Subagent 每次调用使用隔离上下文；researcher 可访问文档、Web 与技能，reviewer 可访问文档与技能，writer 仅访问技能。Worker 不注册 `task`，避免递归委派。

`build_delegation_execution` 只读取实际 AI `task` tool calls 与匹配的 ToolMessage，产出角色、轮次、并行状态、结果和失败状态。UI、trace、metrics 与 eval 共用该事实来源。

Session 拥有 SQLite checkpointer 连接；缓存淘汰和会话删除必须调用 `close()`。数据库中的 thread ID 保证恢复语义。
