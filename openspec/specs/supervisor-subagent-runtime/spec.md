## Requirements

### Requirement: Canonical runtime entry

系统 SHALL 仅通过 `create_agent_session` 组装模型、工具、中间件和 checkpointer。

#### Scenario: 创建 leader session
- **WHEN** application 层请求 paper leader
- **THEN** 返回包含 agent、thread ID、工具清单和资源释放能力的 AgentSession

### Requirement: Bounded subagent delegation

系统 SHALL 通过官方 `SubAgentMiddleware` 暴露 `task`，并按 subagent 配置限制能力。

#### Scenario: 并行独立任务
- **WHEN** leader 在同一 AIMessage 中发出多个 `task` 调用
- **THEN** 系统隔离执行这些 subagent，并将该轮标记为 parallel

#### Scenario: 防止递归委派
- **WHEN** 创建 researcher、reviewer 或 writer
- **THEN** 其工具列表不包含 `task`

### Requirement: Observable delegation

系统 SHALL 从真实 `task` tool-call/result 消息派生委派状态，不得使用启发式或静态角色填充。

#### Scenario: 委派失败
- **WHEN** task ToolMessage 返回错误状态
- **THEN** UI、trace、metrics 和 eval 均显示 failed
