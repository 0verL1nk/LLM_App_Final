# 架构设计

## 目标数据流

```text
Leader Agent ──Markdown + <ui> fragments──> server streaming parser
                                              │         │
                                              │         ├── outside <ui> → message.part.delta
                                              │         └── <ui>         → Pydantic validation → A2UI compiler
                                      ▼
                           ordered SSE events / persisted message parts
                                   │
                                   ▼
              client part renderer: text → surface → text
```

## 生成器契约

模型在单一自然输出流中输出原始 Markdown。仅当需要插入界面时，使用纯 XML 的 `<ui>` fragment。服务端使用有界、状态化的 fragment parser，而不是在 Markdown 上做正则猜测或解析嵌套 JSON。

```md
先说明核心结论。<evidence>doc:chunk_1|p1|o0-10</evidence>

<ui type="research-map">
  <map title="方法脉络">
    <node label="论文">
      <evidence ref="doc:chunk_1" />
      <node label="方法" />
    </node>
  </map>
</ui>

下面展开关键分支与证据。
```

服务端提供 catalog manifest 与本轮证据 ID，模型只决定何时输出 `<ui type="…">` 以及其 type-specific XML 元素。它不生成最终 protocol envelope。标签外的一切内容均是用户可见 Markdown；UI XML 均为私有 transport 内容。

## 自动提示词注入

`A2UIOutputContractBuilder` 在每轮构建 system prompt 时，根据当前 server-registered catalog 自动注入：

- fragment grammar（`<ui type="…">…</ui>`）及禁止将 UI XML 输出到用户正文的规则；
- 每个允许 `type` 的最小 XML schema、尺寸限制和一条短示例；
- 当前 turn 可引用的 `chunk_id` 集合或其受限引用机制；
- “没有明显表达收益时不输出 `<ui>`”的语义指令；
- 当前 A2UI protocol/catalog version。

prompt builder 不手写旧 catalog 细节，也不在 UI 层拼接 prompt。catalog manifest 是生成器与编译器共享的 canonical source；未知版本直接禁用 UI 输出并保留文本回答。

`PresentationDecision` 是服务端从 `<ui>` XML AST 映射出的判别联合：

- `kind="none"`：该回答不值得额外界面；
- `kind="research_map"`：标题、受限树节点、候选 `citation_ids`；
- 后续可显式增加 `claim_evidence_matrix`、`paper_comparison`、`research_timeline`。

模型按语义决定是否输出 `<ui>`，不包含关键词、长度阈值或固定频率。它只能引用 prompt 提供的证据 ID；服务端仍须重新过滤 ID、限制尺寸、并拒绝未知 type。

## 混合消息与时序

每条 assistant message 持久化为有序 `parts`，而非单一 `content` 字符串：

```json
[
  {"id":"part-1","type":"markdown","content":"先说明核心结论。"},
  {"id":"part-2","type":"a2ui","surfaceId":"map-1"},
  {"id":"part-3","type":"markdown","content":"下面展开关键分支与证据。"}
]
```

1. fragment parser 将 `<ui>` 外的每个 token 持续发出为 `message.part.delta`；客户端对该 Markdown part 增量渲染，不等待回答结束。
2. parser 遇到 `<ui type="research-map">` 立刻发送 `message.part.insert`，客户端在当前位置放入 skeleton surface。随后服务端缓冲其最大受限 XML subtree；关闭标签到达时将 XML AST 映射为 `PresentationDecision` 并验证，发送 `createSurface`、`updateComponents`、`updateDataModel`。客户端按 envelope 顺序从 skeleton 渐进切换为 surface。
3. 关闭 `</ui>` 后的 Markdown token 创建新 Markdown part，主 Agent 可以继续自然输出。
4. 缺失关闭标签、未知 type、超出资源上限或 XML schema 失败时，丢弃该 UI buffer 并产生 `presentation.failed`；不得将标签或部分 UI 泄漏给用户。代码围栏中的 `<ui>` 必须按普通 Markdown 文本处理。
5. run 结束时保存完整 part 顺序和 surface snapshot；重连时以 `(runId, sequence)` 重放，不重复插入 part。

`message.part.delta` 与 `message.part.insert` 是 PaperSage 的 transport extension；`<ui>` fragment 仅存在于服务端模型输出边界。A2UI envelope 保持官方 `createSurface`、`updateComponents`、`updateDataModel`、`deleteSurface` 生命周期，不把 Markdown anchor 塞入 A2UI protocol。

不得把不完整 XML subtree 交给 renderer。文字按 token 级流式展示；A2UI 按“已关闭并通过校验的 envelope”粒度渐进展示。这避免半截结构、错误组件或模型文本直接进入 UI，同时仍在模型继续输出后续文字时展示 surface 动效。

客户端按 `(runId, sequence)` 去重、按 `surfaceId` 存储和重放；未知 catalog、非法 envelope 或删除事件只影响对应 surface。已持久化的 assistant message 保存最终 surface snapshot，保证历史会话读取不依赖 SSE。

## 安全与资源边界

- 双端 schema validation；仅注册的 catalog/component/path/action 可以到达 renderer。
- 结构限制：surface 数、节点数、层级、标签/标题长度、引用数、事件总大小与更新频率。
- 每个事实节点仅保留当前 turn 已检索的证据 ID；不可验证内容不带“证据”标识。
- 模型产物不含 HTML、JS、CSS、SVG、任意 URL、函数名或服务端路由。
- XML parser 的错误与映射结果仅存受控日志；用户界面只显示自然回答、验证后的 surface 与用户可读失败状态。

## 迁移与回滚

先建立 XML parser 和无 `<ui>` 的纯文本降级路径，再切换前端与 SSE 事件；最后删除工具 capability 和旧持久化读取兼容代码。每步保持旧会话 snapshot 可读。回滚时关闭 UI parser，继续渲染既有 snapshot，不影响历史会话和主回答。
