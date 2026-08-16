# Run Stream Resilience(SSE 断线自动重连)

## Why

研究回答依赖 SSE 流式推送,事件带 `sequence` 且服务端已支持
`GET /runs/{run_uid}/events?afterSeq=N` 有序重放——协议层为断线恢复做好了
全部准备。但前端当前在流断开时只弹 toast("未能恢复进行中的研究"),靠
1.5 秒轮询兜底恢复"存在进行中 run"的列表;一次网络抖动/电脑休眠/后端
重启,用户看到的就是"断了",研究工具的可靠性叙事在最后一公里破功。

## What Changes

1. **自动重连**:run 流非正常结束(error/close 且 run 未终态)时,自动以
   `afterSeq=lastAppliedSequence` 重连 SSE,指数退避(1s、2s、4s…封顶 30s),
   连接成功即清零退避。
2. **退避上限后降级轮询**:重连尝试达到上限(默认 10 次)后停止重试 SSE,
   切换到既有轮询通道恢复,并显示可见的连接状态;run 进入终态后停止一切
   重连。
3. **连接状态可视化**:统一的连接状态徽标(实时 / 重连中(第 N 次) /
   轮询恢复 / 已停止),基于真实连接事实,禁止伪造进度。
4. **可见性触发恢复**:页面从隐藏切回可见(Page Visibility)时立即尝试
   恢复,不等下一轮退避 tick。

## Non-goals

- 不改服务端 SSE 协议与事件格式(afterSeq 重放已满足)。
- 不做跨设备/多端同步恢复;只管当前页面的 run 流。
- 不接管 durable V2 reducer(durable-research-agent-runtime §6 自带重放
  测试);本变更让 V1 消费路径具备同等韧性,且实现独立于 V2 进度。
- 不做全局网络状态监控(只针对 run 流)。

## Impact

- Web:`web/src/features/research` 的 run 流消费(queries 消费层)与
  live-run reducer 的衔接;连接状态 UI(research-page 流式气泡区);
  轮询兜底路径复用。
- Tests:模拟 EventSource 失败/恢复/终态的 React 测试。
- Docs:README "可恢复的研究过程"条目更新为自动重连语义。
