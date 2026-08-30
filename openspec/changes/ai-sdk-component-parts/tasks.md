# Implementation Tasks

## 后端契约

- [x] `PresentationDecision` 携带 `raw_xml` 原文。
- [x] turn_engine:fragment 打开插入 `component` 部件(streaming),闭合写入原文
  (ready),失败保留部件并记原因(error);移除 surface 构建、surfaceId 配对、
  悬空部件过滤与 `a2ui_surface/a2ui_surfaces/mindmap_data` 结果字段。
- [x] 投影层:`answer_part_insert/delta` → `component` item 生命周期事件。
- [x] research_workspace:完成态补发 `component` item.completed(含最终 xml);
  新消息 a2ui 数组写空;旧 run 回放与 a2ui_surfaces 兼容路径保留。
- [x] `TurnCoreResult` 契约类同步。

## 前端渲染

- [x] `live-run`:component 部件归约(created/delta/completed,终态不回退),
  `assistantParts` 透传持久化 component 部件。
- [x] `research-map.ts`:XML 解析器,子节点/标签上限截断而非丢弃。
- [x] `component-parts.tsx`:注册表渲染(streaming 骨架 / ready 解析成树 /
  error 与未知组件说明行)。
- [x] `a2ui-mindmap.tsx` 拆出共享 `MindmapTree`;legacy surface 走原路径。
- [x] research-page 渲染循环接入 component 分支。

## 测试

- [x] turn_engine:ready 部件携带原文、error 部件保留、legacy 断言更新。
- [x] research_run_events:component item.completed 事件断言。
- [x] 前端:research-map 解析器(完整/截断/不可识别)、component 部件流式归约、
  error 保留、持久化透传。
- [x] 全量后端单测(365 passed)与全量 vitest(38 passed)通过;债务棘轮内(research_workspace 679/679,test_turn_engine 拆出 test_turn_component_parts)。
