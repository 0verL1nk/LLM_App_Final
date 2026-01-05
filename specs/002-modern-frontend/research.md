# Research: 现代前端重构 (Modern Frontend Refactor)

## Decisions & Rationales

### 1. 实时通信: WebSocket (`/ws/tasks`)
- **Decision**: 建立全局 `useWebSocket` hook，对接后端现有 WS 接口。
- **Rationale**: 后端已具备完善的推送能力。通过全局 hook，当任何任务（总结、思维导图等）状态更新时，前端能立即响应并刷新相关 UI。
- **Alternatives**: Server-Sent Events (SSE) - 后端不支持；Polling - 性能较差。

### 2. UI 交互: Workspace (工作空间) 模式
- **Decision**: 借鉴 PDF 阅读器 + AI 侧边栏布局。左侧 PDF.js 阅读器，右侧可切换的 Tabs (总结/问答/改写/思维导图)。
- **Rationale**: 用户重度依赖原文内容。集中式布局减少了视觉跳跃，增强了“助手”感。
- **Alternatives**: 独立功能页面 - 会导致用户频繁返回列表页，体验支离破碎。

### 3. 思维导图布局: 自动布局 (Auto-layout)
- **Decision**: 使用 `dagre` 或 `flex-tree` 配合 React Flow 实现。
- **Rationale**: 文献思维导图节点较多，手动调整不现实。自动布局确保逻辑层次清晰（如：中心思想 -> 分支观点）。
- **Alternatives**: 手动拖拽保存 - 开发成本高且用户并不需要长期维护图的位置。

### 4. 样式主题: Indigo 科技感
- **Decision**: 选用 Indigo 作为主色调，Slate 作为背景灰度。
- **Rationale**: Indigo 代表智慧与科技，符合 AI 文献阅读工具的定位。

## Best Practices
- **React 19**: 利用 `Suspense` 处理加载状态，结合 TanStack Query 的 `useSuspenseQuery`。
- **Tailwind**: 使用 `tailwind-merge` 和 `clsx` (shadcn 标准) 处理动态类名。
- **Accessibility**: 确保思维导图节点支持键盘聚焦，Markdown 内容具备良好的阅读对比度。
