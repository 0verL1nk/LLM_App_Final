# Proposal: AI SDK 式 component parts(a2ui 内容契约改造)

## Why

现行 a2ui 链路把"生成式 UI"的解析、构建、校验全部放在服务端:模型在正文里写
`<ui type="research-map">` XML,后端拦截后在服务端构建 surface 对象,经 surfaceId
把 parts 指针与 a2ui 数组配对,再经独立 SSE presentation 层下发。同一份数据存在
parts 指针、a2ui 数组、mindmap_data 遗留字段、SSE 事件四份表示,渲染逻辑长在
服务端。后果是三类真实故障:校验失败整图丢弃("有时候没有")、配对脱节导致
空白卡(1.8.x 排查两天的根因)、新旧表示漂移。

## What Changes

对齐 Vercel AI SDK 的 message.parts 契约:**后端只存内容,前端拥有渲染**。

1. parts 新增 `component` 部件:`{id, type:"component", component:"research-map",
   state:"streaming"|"ready"|"error", xml, error?}`——XML 原文逐字保存,不构建
   UI 对象。
2. 服务端退役:`build_mindmap_surface_from_request` 的存储路径、surfaceId 配对、
   `a2ui_surface/a2ui_surfaces/mindmap_data` 结果字段、a2ui 数组写入(新消息写
   空数组,旧消息兼容读取)。
3. 事件投影:`answer_part_insert/delta` 映射为 `component` item 生命周期事件
   (created → delta(state+xml) → completed),替代 presentation 通道。
4. 前端:`live-run` 归约 component 部件(终态不被流式事件回退);`research-map.ts`
   解析 XML(上限改为截断而非丢弃);`ComponentPart` 注册表渲染,未知组件与错误
   态显示说明行;旧消息的 a2ui surface 走 legacy 路径继续渲染。
5. 失败不再吞图:fragment 校验失败保留 error 部件与正文,显示原因。

## Impact

- 协议:`agent/application/a2ui_fragments.py`、`turn_engine.py`、`run_timeline.py`、
  `research_workspace.py`、`contracts.py`
- 前端:`web/src/lib/live-run.ts`、`research-map.ts`(新)、`component-parts.tsx`(新)、
  `a2ui-mindmap.tsx`(拆出 MindmapTree)、`research-page.tsx`
- 兼容:已存库的 a2ui surface 消息渲染不受影响;重连回放旧 run 的 presentation
  事件继续受支持
