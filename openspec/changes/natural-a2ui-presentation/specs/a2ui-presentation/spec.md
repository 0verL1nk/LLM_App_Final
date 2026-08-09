## ADDED Requirements

### Requirement: 主研究 Agent 不感知 A2UI 工具

系统 SHALL 不向 Leader Agent 注册 A2UI 工具。Leader SHALL 输出自然 Markdown，并仅用纯 XML 的 `<ui type="…">` fragment 标记私有 UI 结构；服务端负责 protocol 编译。

#### Scenario: 正常研究回答
- **WHEN** Leader Agent 完成一轮研究回答
- **THEN** `<ui>` 外内容仅包含用户可读 Markdown 和引用
- **AND THEN** `<ui>` XML 不得透传到用户正文
- **AND THEN** 不包含 A2UI tool call 或原始 protocol envelope

### Requirement: A2UI 必须作为消息内联 part 渲染

系统 SHALL 将 A2UI surface 作为 assistant message 的有序 content part，使自然文字可在 surface 前后继续流式输出。

#### Scenario: 回答中途出现可视化
- **WHEN** output stream 中出现并关闭一个有效的 `<ui type="research-map">` payload
- **THEN** 服务端发送带稳定 part ID 的 `message.part.insert` 和对应 A2UI lifecycle events
- **AND THEN** 客户端在该 part 的顺序位置渲染 surface
- **AND THEN** 后续 Markdown delta 追加到新的或已有 Markdown part，而不是被延迟到回答结尾

### Requirement: XML output contract 必须自动注入

系统 SHALL 从当前 server-registered catalog 构建 `<ui>` output contract，并在每轮模型调用时注入 system prompt。

#### Scenario: 支持的 A2UI catalog
- **WHEN** 当前模型调用启用已注册的 A2UI catalog
- **THEN** system prompt 包含 `<ui>` fragment grammar、允许 type、对应 schema、版本和安全边界
- **AND THEN** prompt 不包含手写的过期 catalog 或前端实现细节

#### Scenario: UI 流式渲染
- **WHEN** parser 收到 `<ui>` 外的 Markdown token
- **THEN** 客户端立即向对应 Markdown part 增量渲染该 token
- **WHEN** parser 收到有效 `<ui type="…">` 开标签
- **THEN** 客户端在对应 part 位置显示 loading surface
- **WHEN** UI payload 关闭并通过校验
- **THEN** 客户端按完整、已验证的 A2UI envelope 渐进渲染 surface

#### Scenario: UI payload 不完整
- **WHEN** stream 在 `</ui>` 前结束、代码围栏外 XML 未通过 type-specific schema validation，或 type 不受支持
- **THEN** 服务端丢弃该 UI buffer 并发送 `presentation.failed`
- **AND THEN** 已经发送的 Markdown 内容保持可见，UI XML 不得显示给用户

### Requirement: 模型输出的 UI fragment 必须由服务端映射和校验

系统 SHALL 将已关闭的 `<ui>` XML subtree 映射为 `PresentationDecision` 并在服务端校验后生成 surface。

#### Scenario: 文本已足够
- **WHEN** 模型未输出 `<ui>` fragment
- **THEN** 系统持久化并显示正常回答
- **AND THEN** 不创建 surface

#### Scenario: 层级信息适合地图
- **WHEN** 模型输出有效 `type="research-map"` XML subtree
- **THEN** 服务端仅使用注册 catalog 编译并发送 A2UI envelope
- **AND THEN** 正常回答保持不变，导图在 `<ui>` 所在的消息位置显示

### Requirement: surface 必须可追溯且安全

系统 SHALL 仅把当前 turn 已检索的证据绑定到 surface，并拒绝不受支持的 renderer 指令。

#### Scenario: 模型提供伪造证据
- **WHEN** 决策中的 `citation_ids` 不在当前已检索证据集合
- **THEN** 服务端丢弃这些 ID
- **AND THEN** 不伪造来源、页码或链接

#### Scenario: UI fragment 无效
- **WHEN** XML parser 收到无效结构、超出资源限制或未知 type
- **THEN** 系统记录 `presentation.failed` 事件并保留正常回答
- **AND THEN** run 不得因表现层失败而失败

### Requirement: 有序事件可恢复

系统 SHALL 将验证后的 surface lifecycle 作为有序 run events 持久化并支持重放。

#### Scenario: 用户在 surface 生成期间重新进入会话
- **WHEN** 客户端使用 `afterSeq` 重连
- **THEN** 服务端按 sequence 重放 `ui.a2ui` 事件
- **AND THEN** 客户端仅更新匹配的 `surfaceId`，不重复渲染已有 event
