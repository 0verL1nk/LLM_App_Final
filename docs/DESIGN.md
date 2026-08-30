# UI/UX 约定

`web/` 的界面约定。前端工程约定（路由/数据/分层）见 [FRONTEND.md](FRONTEND.md)；
A2UI 协议细节见 [architecture/a2ui.md](architecture/a2ui.md)。

## 生成式界面（A2UI）契约

- 模型不调用 UI 工具、不输出 A2UI JSON；它在正文中按需内联
  `<ui type="research-map">…</ui>` 片段。
- 服务端流式剥离私有片段：闭合且通过 Pydantic schema 校验后才编译为稳定
  A2UI v0.9.1 envelope 并发 `ui.a2ui` 事件；无效输入回退普通回答，绝不替换答案。
- 思维导图节点可带 `citation_ids`，但服务端只保留本轮真实检索到的 chunk ID；点击走
  现有证据检查器，模型提供的 URL/代码到不了客户端。
- 新增 catalog（对比矩阵、时间线等）必须同样证据接地，不得暴露通用渲染能力。

## 证据引用渲染

- 回答中的 `<evidence>` 契约（见 [product-specs/research-workflow.md](product-specs/research-workflow.md)）
  在前端渲染为行内 `[n]` 引用（`evidence-inline-citations.tsx`）。
- 点击引用打开证据检查器：按页预览 PDF 页面并按页码 + bbox 高亮定位
  （`evidence-preview.tsx`，预览图来自 `/documents/{doc_uid}/preview/{page}`）。
- 跨任务证据合并（claims/开放问题/未决冲突）在检查器展示，读自持久化
  `evidence_merge` 产物，不由前端推断。

## 组件栈

- shadcn/ui 源码组件（Radix 原语）+ Tailwind 设计令牌 + Lucide 图标，克制的编辑式
  工作区主题；组件源码进仓（`web/src/components/ui/`），不用黑盒包。
- 桌面端持久应用栏 + 上下文检查器；移动端用 Radix sheet 提供会话切换与新建，
  composer 尊重安全区，上下文标签页滚动而非裁剪。
- 空/加载/错误/破坏性状态是一等 UI，不允许只设计"正常路径"。

## 文案

界面文案默认中文（与域提示、产品语言一致）；错误信息要说明"发生了什么、用户能做什么"，
禁止裸异常文本。数值进度（摄取百分比等）只展示服务端真实度量的数字。

## 流式渲染与 <think> 分流

- Run 事件按序应用（`live-run.ts`）：`reasoning` 分片与 markdown 分片是不同的
  message part——思考内容折叠展示，不与正文混排；A2UI surface 在正文中间占位，
  前后文字立即可见。
- 断线后客户端按事件序号重放恢复（`afterSeq` 游标），surface 按 `surfaceId`
  独立恢复，不需要重新解析模型文本。

## 状态展示红线

面向用户的运行状态（进度、来源、context 用量、任务队列）只能来自
Run/RunItem/Task 服务端事实（AGENTS.md §3.16）：前端禁止 mock、禁止本地推算或
补齐"看起来合理"的中间态。
