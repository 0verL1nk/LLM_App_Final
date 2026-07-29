# 实现任务

- [x] 删除 A2A、TeamRuntime、orchestration coordinator 和相关工具
- [x] 建立 canonical `create_agent_session` 入口
- [x] 接入官方 `SubAgentMiddleware` 与 `task` 工具
- [x] 校验文件式 subagent 配置并限制角色工具
- [x] 禁止 worker 递归委派
- [x] 从真实消息构建 delegation trace、指标和 UI
- [x] 将 eval 改为委派角色、数量和并行度契约
- [x] 移除策略路由设置及废弃运行时配置
- [x] 明确 checkpointer 连接所有权和释放路径
- [x] 更新 README、架构文档和 OpenSpec
- [x] 通过完整质量门禁
