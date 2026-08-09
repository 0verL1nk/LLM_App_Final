# 实现任务

- [ ] 定义纯 XML 的 `<ui type="…">` fragment grammar、每种 type 的 XML schema、`PresentationDecision`、catalog manifest 与严格 Pydantic schema。
- [ ] 新增 `A2UIOutputContractBuilder`，由当前注册 catalog/version 自动注入每轮 system prompt，并为无兼容 catalog 的模型安全降级为纯 Markdown。
- [ ] 实现有界、增量 XML fragment parser；仅将 `<ui>` 外 Markdown 转发为正文，将已闭合 UI subtree 映射/校验为 DTO，并忽略代码围栏内的标签。
- [ ] 将决策编译为 A2UI v0.9.1 envelope；统一服务端校验、证据过滤和资源限制。
- [ ] 定义 `message.part.delta`、`message.part.insert` 和 `a2ui` part anchor 的服务端/前端 transport contract。
- [ ] 在 run worker 中接入 `presentation.started/completed/failed` 与按序 `ui.a2ui` 事件，确保 surface 不阻塞文字流。
- [ ] 更新消息 snapshot、SSE 恢复和前端 part/surface store；Markdown token 级渲染，`<ui>` 开标签插入 skeleton，验证后的 envelope 渐进替换，保证 text → surface → text 的顺序、多 surface、删除、去重和重放。
- [ ] 删除 `a2ui_pack`、`present_research_surface`、相关 prompt/skill 指令和工具化测试；以 XML output contract 替代。
- [ ] 为 `none`、有效导图、伪造证据、模型失败、重连重放和历史兼容增加单元/集成/eval 测试。
- [ ] 接入面向研究回答的 catalog：导图、证据矩阵、论文比较、时间线；每项先定义 evidence contract。
- [ ] 更新 README、架构文档和用户可见的失败文案。
- [ ] 运行核心质量门禁、前端测试、端到端恢复测试和 A2UI schema contract eval。
