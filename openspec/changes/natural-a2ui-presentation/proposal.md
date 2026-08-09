# 自然式 A2UI 表现层

## 背景

当前实现将 `present_research_surface` 暴露为 Leader Agent 工具。虽然输入被校验，但表现层选择混入了研究 Agent 的工具规划，且 surface 在主回答结束后才产生。这不符合“用户先得到自然回答，系统在合适时补充可交互表达”的产品体验。

## 目标

1. Leader Agent 不调用 A2UI 工具；它输出自然 Markdown token 流，并仅在需要时内联纯 XML 的 `<ui type="…">` fragment，catalog/protocol 编译细节仍不进入模型工具规划。
2. 聊天消息使用有序的混合 content parts：自然文字可以在生成途中插入 A2UI surface，再继续文字。
3. 服务端从已闭合的 `<ui>` subtree 映射出受 Pydantic schema 约束的产品级 `PresentationDecision`，再编译为稳定 A2UI v0.9.1 envelope。
4. UI 与正文同属一个流式消息；生成失败不得影响回答、引用、会话持久化或 run 的终态。
5. 仅允许本地 catalog、已检索证据和 allowlist action；客户端绝不执行模型提供的代码或 URL。
6. 每轮自动注入与当前 catalog/version 一致的 XML output contract；前端按 token/SSE 流渲染，不等待完整回答。

## 非目标

- 不从自然 Markdown 使用正则或关键词推断 UI；仅解析定义明确的 XML framing。
- 不让模型直接生成 HTML、React、CSS、JavaScript 或未校验的 A2UI JSON。
- 不在本变更中加入任意可执行 action、表单写入或远程页面嵌入。
- 不将 A2UI 用作 chain-of-thought 或替代研究正文。

## 影响

删除 Leader 的 `a2ui_pack` capability、`present_research_surface` 工具和相关 prompt/skill 指令。新增应用层 XML-to-decision compiler、持久化/事件契约和面向研究任务的 surface eval。
