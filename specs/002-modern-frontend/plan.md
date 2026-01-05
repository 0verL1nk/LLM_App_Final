# Implementation Plan: 现代前端重构 (Modern Frontend Refactor)

**Branch**: `002-modern-frontend` | **Date**: 2026-01-05 | **Spec**: [/specs/002-modern-frontend/spec.md](/specs/002-modern-frontend/spec.md)
**Input**: Feature specification from `/specs/002-modern-frontend/spec.md`

## Summary

重构现有的 React 前端，采用 **shadcn/ui** (Indigo 主题) 和 **TailwindCSS** 构建现代化工作空间模式（Workspace）。核心技术栈包括 **React Flow** (思维导图)、**Zustand** (全局状态管理) 和 **TanStack Query** (API 缓存)。系统将通过 **WebSocket** 实现实时的任务进度推送，并整合文献阅读器与 AI 处理工具侧边栏，提供沉浸式的学术阅读体验。

## Technical Context

**Language/Version**: React 19, TypeScript 5.4+  
**Primary Dependencies**: shadcn/ui, TailwindCSS, Framer Motion, @xyflow/react (React Flow), Zustand, @tanstack/react-query, Lucide React, react-markdown  
**Storage**: 后端数据库存储 (API Key, 用户偏好), LocalStorage (Auth Token)  
**Testing**: Vitest, Playwright (推荐用于 UI 集成测试)  
**Target Platform**: Modern Browsers, Desktop-first (optimized for Workspace mode)  
**Project Type**: Web Application  
**Performance Goals**: < 1.5s 首屏渲染, < 300ms 主题切换延迟, WebSocket 延迟 < 50ms  
**Constraints**: 必须保持与现有 FastAPI 后端 (/api/v1) 的 API 契约一致性。  
**Scale/Scope**: ~10 核心页面，复杂的交互式思维导图与长文本渲染。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **现代化 UI**: 必须使用 shadcn/ui 和 TailwindCSS 确保设计一致性。
- [x] **状态分离**: UI 状态由 Zustand 管理，服务器数据由 TanStack Query 管理。
- [x] **实时性**: 任务进度必须通过 WebSocket 同步，不允许轮询。
- [x] **沉浸式体验**: 详情页采用 Workspace 布局，原文与 AI 工具同屏。

## Project Structure

### Documentation (this feature)

```text
specs/002-modern-frontend/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── components/
│   │   ├── ui/          # shadcn/ui 组件
│   │   ├── layout/      # Workspace, Sidebar, Header
│   │   ├── features/    # Chat, Mindmap, Rewrite, Summary (业务组件)
│   │   └── common/      # Markdown, ThemeToggle, StatCard
│   ├── pages/           # Login, Dashboard, Documents, Workspace
│   ├── hooks/           # useWebSocket, useAuth, useTasks
│   ├── stores/          # authStore, uiStore, fileStore
│   ├── services/        # API clients (axios/fetch wrappers)
│   ├── types/           # TypeScript definitions
│   └── lib/             # cn utility, react-flow-utils
└── public/              # 静态资源
```

**Structure Decision**: 采用 **Feature-based** 目录结构。核心 AI 功能（如问答、总结）被封装在 `features/` 下，便于在 `Workspace` 页面中作为侧边栏组件复用。

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| WebSocket Integration | Real-time progress | Polling increases server load and lacks "instant" feel. |
| React Flow Auto-layout | User convenience | Manual node management is tedious for transient AI results. |
| Workspace Pattern | Deep reading workflow | Tab switching breaks context and cognitive flow. |
