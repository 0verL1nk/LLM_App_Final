# Execution Mode Transparency(透出实际执行模式与路由原因)

## Why

用户每轮可以在 自动 / ReAct / Plan-Execute / Agent Teams 中选择执行模式,
后端用确定性的 `resolve_execution_route` 解析并**随 Run 持久化**了
`requested_mode / resolved_mode / reason`(如 auto 下的关键词路由、无效
输入的 fallback),但 UI 只在下拉框显示用户选了什么——实际走了哪条路、
为什么,用户完全看不到。选了 "Agent Teams" 却因旗标未开静默走了别的路,
或 auto 被关键词判成 teams,用户无从知晓也无从纠错(改措辞或手动指定)。
这是"研究可以延续、状态可解释"产品叙事的一个盲点。

## What Changes

1. **Run 事实透出**:确认 run 详情/事件侧暴露持久化的路由三元组
   (requested/resolved/reason),历史会话重载同样可得;不依赖仅存在于
   POST 响应中的内存数据。
2. **消息级徽标**:每条助手消息显示小的模式徽标:auto 请求显示
   "Auto → ReAct · 直接请求"式样;显式选择显示所选模式;无效输入被
   fallback 时显示原因。
3. **检查器详情**:run 检查器显示完整路由记录(请求/实际/原因/时间)。
4. **文案映射**:reason 码到稳定中文文案的映射表;未知 reason 显示原文,
   不猜测。

## Non-goals

- 不改路由规则本身(关键词启发式是否合理是另一个话题)。
- 不做"每步展示模型内部决策";只透出已持久化的确定性路由事实。
- 不为旧版本没有路由记录的历史 run 编造显示(无记录则不显示徽标)。

## Impact

- Backend:确认/补充 run 详情接口的路由字段(数据已持久化,预计只有
  序列化缺口)。
- Web:research-page 消息徽标、research-inspector run 详情、schemas 类型。
- Tests:有/无路由记录的渲染测试。
- Docs:README Agent 设计表补一行。
