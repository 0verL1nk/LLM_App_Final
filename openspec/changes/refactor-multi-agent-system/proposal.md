# Supervisor/Subagent 运行时重构

## 背景

旧主链同时保留 A2A coordinator、TeamRuntime、策略路由和多层 facade，执行语义重复，UI 指标也无法证明真实委派。

## 目标

1. 只保留 `create_agent_session` 一个 canonical 构造入口。
2. 采用 Deep Agents `SubAgentMiddleware` 的 `task` 工具实现上下文隔离委派。
3. 以配置声明 researcher、reviewer、writer，并按角色限制工具。
4. 从真实 tool-call/result 消息生成委派状态、trace、指标和 eval。
5. 删除 A2A、TeamRuntime、关键词策略路由与无语义 wrapper。

## 非目标

本地 Streamlit 运行时不伪装成 durable background worker。需要跨进程、可恢复的异步执行时，应引入独立队列/工作流基础设施，而不是线程池和全局字典。
