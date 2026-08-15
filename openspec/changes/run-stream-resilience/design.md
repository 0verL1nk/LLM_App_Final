# Design: Run Stream Resilience

## 1. Design decisions

### 1.1 重连状态机(单一事实源)

每个进行中的 run 流由一个小状态机管理,状态即 UI 数据源:

```text
live ──(error/close 且 run 未终态)──> reconnecting(attempt=1..N)
reconnecting ──(SSE 成功)──> live(退避清零)
reconnecting ──(attempt ≥ N)──> polling(既有 1.5s 轮询通道)
polling ──(轮询发现 run 仍在进行,可周期性再试 SSE)──> live
任意态 ──(终态事件/终态轮询结果)──> closed(停止一切重试)
```

- 触发重连的错误分类:网络 error、stream 提前 close、HTTP 非 200。
- 终态判定以**事件流中的终态事件**或轮询返回的 run 状态为准,不凭
  "长时间没新事件"猜测(避免把慢模型当成断线)。
- 退避:1s 起步 ×2,封顶 30s,加 ±20% 抖动(多标签页场景避免同步风暴);
  连接成功清零。

### 1.2 去重与顺序由既有 reducer 保证

live-run reducer 已按 sequence 去重并缓冲乱序事件;重连重放是它的既有
输入形态("A reconnect may replay events"),本变更不触碰 reducer 语义,
只负责把重连变成自动行为。断线期间到达的事件通过 afterSeq 重放补齐,
不请求全量。

### 1.3 状态可见但克制

流式气泡区顶部一枚状态徽标:实时(默认不显示)/ 重连中 · 第 N 次 /
已切换轮询恢复 / 连接已断开。文案中文、简短;**不显示伪造的进度或
"思考中"动画冒充连接状态**(AGENTS.md 约束 16)。toast 仅保留为
"降级轮询"与"最终失败"两个真实状态的提示,不再承担重连职责。

### 1.4 页面可见性即时恢复

`visibilitychange → visible` 时:若处于 reconnecting/polling 且 run 未
终态,立即发起一次恢复尝试(跳过剩余退避等待)。休眠唤醒场景(桌面
Electron 常见)由此覆盖。

## 2. Alternatives considered

- **只加强轮询(不做 SSE 重连)**:否决——轮询拿不到增量渲染粒度,回答
  会从"流式"退化为"整段出现",体验降级明显。
- **服务端推送心跳 + 断线检测**:心跳能更快发现假死连接,但先解决
  客户端不重连的问题;心跳列为后续增强,不进本变更。

## 3. Testing

- 模拟 EventSource 在中途 error:自动重连、afterSeq 正确、无重复渲染。
- 连续失败至上限:状态变 polling、轮询恢复后无重复;终态后停止重试。
- 可见性切换:reconnecting 态下切回标签页立即恢复。
- 退避抖动不破坏 attempt 计数与清零逻辑。
