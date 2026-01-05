# Feature Specification: 现代前端重构 (Modern Frontend Refactor)

**Feature Branch**: `002-modern-frontend`  
**Created**: 2026-01-05  
**Status**: Draft  
**Input**: User description: "创建前端现代化重构规格说明。目标：使用 shadcn/ui (Indigo 主题), React Flow (思维导图), 支持明暗模式, Zustand 状态管理, TanStack Query。对接现有的 FastAPI 后端。页面包括：登录/注册、仪表盘、文献列表、文件详情、AI 总结、问答、改写、思维导图、设置。"

## Clarifications

### Session 2026-01-05

- Q: 实时进度更新机制如何实现？ → A: 使用 WebSocket 对接现有后端接口。
- Q: “文本改写”页面的交互模式？ → A: 采用左右双栏对比布局，且两侧文本均可编辑，默认开启同步滚动。
- Q: API Key 存储方式？ → A: 对接后端 API 存储于数据库。
- Q: 思维导图位置是否持久化？ → A: 采用纯自动布局，无需保存位置。
- Q: 文献处理集成方式？ → A: 采用集中式工作空间（Workspace）模式，整合阅读与 AI 工具。选中 PDF 文本时显示悬浮菜单，支持发送至 AI 任务。
- Q: 文献上传行为？ → A: 支持拖拽多个文件进行并发上传。
- Q: AI 处理结果持久化？ → A: 所有 AI 生成的结果（总结、问答、改写等）均自动保存至后端数据库。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 基础认证与仪表盘 (Priority: P1)

作为一名研究人员，我希望能够安全地登录系统并查看我的文献阅读概览，以便快速进入工作状态。

**Why this priority**: 认证是访问系统的基础，仪表盘提供全局视野，是用户体验的第一步。

**Independent Test**: 用户可以通过表单注册和登录，成功后跳转至包含统计卡片和上传区域的仪表盘。

**Acceptance Scenarios**:

1. **Given** 用户未登录，**When** 访问应用，**Then** 看到美观的登录/注册分屏页面。
2. **Given** 提供正确的凭据，**When** 点击登录，**Then** 进入仪表盘，看到支持多文件拖拽上传的统计和最近阅读记录。
3. **Given** 已登录状态，**When** 点击切换主题，**Then** 界面即时在明色和暗色模式间切换，且 Indigo 主题色保持一致。

---

### User Story 2 - 文献管理与 AI 处理 (Priority: P1)

作为一名用户，我希望能够上传 PDF/Word 文献，并使用 AI 生成总结和进行问答，以便高效理解复杂内容。

**Why this priority**: 这是应用的核心价值所在，即通过 AI 辅助阅读。

**Independent Test**: 上传一个文件，启动 AI 总结任务，并看到结构化的 Markdown 总结结果且自动保存。

**Acceptance Scenarios**:

1. **Given** 在仪表盘或文献列表，**When** 拖入多个 PDF 文件，**Then** 看到实时并发上传进度条。
2. **Given** 已上传的文件，**When** 点击“总结”，**Then** 看到 AI 处理进度，完成后展示包含要点和分段摘要的页面，且刷新后结果仍然存在。
3. **Given** 文献详情页，**When** 输入关于文档的问题，**Then** 看到类似聊天的交互界面展示 AI 的详细回答及来源引用。选中 PDF 文本时能通过悬浮菜单快速提问。

---

### User Story 3 - 思维导图可视化 (Priority: P2)

作为一名视觉学习者，我希望将文献结构可视化为思维导图，以便更好地把握文章逻辑。

**Why this priority**: 差异化功能，提供非文本的分析视角。

**Independent Test**: 点击生成思维导图，看到 React Flow 渲染的交互式节点图。

**Acceptance Scenarios**:

1. **Given** 完成分析的文献，**When** 进入思维导图页面，**Then** 看到由 React Flow 渲染的树状或图状结构。
2. **Given** 思维导图，**When** 缩放或平移，**Then** 操作流畅且节点清晰可见。

---

### Edge Cases

- 当后端任务处理时间过长（超过 5 分钟）时，前端如何优雅地显示超时或后台运行状态？
- 如果用户在处理过程中意外刷新页面或断网，Zustand 状态如何恢复或显示任务继续？
- 处理超大文件（50MB+）或纯图片无 OCR 的 PDF 时，前端如何提示不支持或处理失败？

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须提供基于 shadcn/ui 的 Indigo 调色板，并完整支持 Light/Dark 模式。
- **FR-002**: 必须集成 React Flow 用于思维导图的可视化渲染，支持节点的缩放和平移，并使用自动布局算法（Auto-layout）呈现文献结构。
- **FR-003**: 必须使用 TanStack Query 管理 API 请求，实现自动缓存、预取和处理中的加载状态显示。
- **FR-004**: 必须使用 Zustand 管理全局 UI 状态（如侧边栏收缩、主题、当前选中的文件）和认证状态。
- **FR-005**: 页面必须包含：
    - 登录/注册（分屏设计）
    - 仪表盘（统计卡片 + 快速上传，支持多文件拖拽）
    - 文署列表（支持搜索、筛选、分页的数据表格）
    - 文件详情（集中式工作空间，整合阅读器与 AI 工具侧边栏，支持文本选中悬浮菜单）
    - AI 功能区（总结、聊天问答、文本改写（双栏对比且支持同步滚动，两侧均可编辑）、思维导图）
    - 设置（API Key 同步后端、模型偏好、账户信息）
- **FR-006**: 必须使用 WebSocket 对接后端 `/ws/tasks` 接口，实现任务进度的实时推送与全局状态更新。
- **FR-007**: 系统必须确保所有 AI 生成的内容均自动异步保存至后端。

### Key Entities

- **UserSession**: 包含 JWT 令牌、用户信息和 API 配置。
- **FileDocument**: 包含文件元数据、处理状态、提取的文本及 AI 生成的内容（总结、问答历史）。
- **AnalysisTask**: 代表后台运行的 AI 任务，包含任务 ID、类型、进度百分比和状态。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 页面加载速度（首屏渲染）在标准网络环境下小于 1.5 秒。
- **SC-002**: 在明暗模式切换时，UI 组件的过渡时间小于 300ms 且无闪烁。
- **SC-003**: 95% 的用户可以在不查看帮助文档的情况下完成文件上传并启动 AI 总结任务。
- **SC-004**: 系统能够流畅渲染包含至少 50 个节点的复杂思维导图，无明显掉帧。
