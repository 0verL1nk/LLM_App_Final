## ADDED Requirements

### Requirement: Canonical session construction

系统 SHALL 仅通过 `create_agent_session` 组装模型、能力、中间件与 checkpointer。

#### Scenario: 创建 leader session

- **WHEN** application 层请求 paper leader
- **THEN** 系统返回拥有 agent、thread ID、工具清单与资源释放能力的 AgentSession

### Requirement: Bounded subagent delegation

系统 SHALL 通过 Deep Agents `SubAgentMiddleware` 提供 `task`，并按角色限制 subagent 能力。

#### Scenario: 并行独立任务

- **WHEN** leader 在同一模型响应中发出多个互不依赖的 `task` 调用
- **THEN** 系统隔离执行调用，并将该委派轮次记录为 parallel

#### Scenario: 禁止递归委派

- **WHEN** 创建 researcher、reviewer 或 writer
- **THEN** 其工具清单不包含 `task`

### Requirement: Runtime-derived observability

系统 SHALL 从真实 `task` tool-call 与匹配的 ToolMessage 派生委派状态。

#### Scenario: 委派失败

- **WHEN** task ToolMessage 返回错误
- **THEN** trace、UI、metrics 与 eval 统一显示 failed
