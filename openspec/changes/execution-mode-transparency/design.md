# Design: Execution Mode Transparency

## 1. Design decisions

### 1.1 数据源是服务端 Run 事实,不是提交响应

`ExecutionRoute`(requested_mode / resolved_mode / reason)在 run 创建时
解析并随 Run 持久化(`agent/application/execution_routing.py` 文档明言
"The server-side mode decision recorded with a Run")。UI 显示的唯一数据源
是 run 详情/事件返回的持久化值;POST run 的响应只用于即时反馈,刷新与
历史回看走 run 查询。若发现 run 详情序列化缺少该字段,补序列化,不新建
第二份存储。

### 1.2 徽标形态:一行小字,不是弹窗

助手消息头部(时间戳旁)一行小徽标:

- 显式选择:`ReAct` / `Plan-Execute` / `Agent Teams`(等宽小标签,无箭头
  ——所见即所选,但仍显示,因为历史回看时用户不记得当时选了什么)。
- auto 解析:`Auto → ReAct`式样,hover/focus 展开原因文案。
- fallback(如 invalid_override_fallback):徽标加警示色,一眼可见
  "我选的没生效"。

### 1.3 reason 码 → 文案的静态映射

reason 是代码里的稳定枚举(`user_selected` / `invalid_override_fallback` /
`independent_comparison_or_review` / `multi_step_or_long_request` /
`bounded_direct_request`)。维护一张中文映射表;未知码显示原始码。不做
自由文本渲染(reason 来自自家代码,非模型生成,但防御性保留原文回退)。

### 1.4 缺失即缺失

升级前的历史 run 没有路由记录:徽标不渲染,检查器该节显示"无记录"。
禁止前端按消息内容反推模式(AGENTS.md 约束 16 的精神:状态来自服务端
事实,不猜测)。

## 2. Testing

- 有路由记录:徽标与检查器显示三元组;auto/显式/fallback 三种形态。
- 无路由记录:不渲染徽标,检查器显示无记录。
- reason 未知码:显示原始码不崩溃。
- 历史会话重载与流式首屏显示一致。
