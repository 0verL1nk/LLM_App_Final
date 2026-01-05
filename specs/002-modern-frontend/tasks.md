# Tasks: 现代前端重构 (Modern Frontend Refactor)

**Input**: Design documents from `/specs/002-modern-frontend/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Implementation Strategy**: 先交付 MVP（认证 + Dashboard + 文献列表 + Workspace 基础），再逐步补齐 AI 面板与思维导图。

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Initialize shadcn/ui in `frontend/components.json`
- [x] T002 [P] Install dependencies in `frontend/package.json` (zustand, @tanstack/react-query, next-themes, @xyflow/react, react-hook-form, zod, react-markdown, react-pdf, framer-motion, lucide-react)
- [x] T003 [P] Configure Tailwind CSS and shadcn theme tokens in `frontend/tailwind.config.js` and `frontend/src/index.css`
- [x] T004 [P] Define environment variables in `frontend/.env.example` (VITE_API_BASE_URL, VITE_WS_BASE_URL)
- [x] T005 [P] Create `cn` utility helper in `frontend/src/lib/utils.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [x] T006 Define shared TypeScript interfaces in `frontend/src/types/index.ts` (User, File, Task, Auth)
- [x] T007 [P] Implement Axios/Fetch wrapper with interceptors in `frontend/src/services/http.ts`
- [x] T008 [P] Implement Authentication store in `frontend/src/stores/authStore.ts` (Zustand)
- [x] T009 [P] Implement UI state store in `frontend/src/stores/uiStore.ts` (Zustand: sidebar, theme, activeTool)
- [x] T010 [P] Set up TanStack Query provider in `frontend/src/components/providers/QueryProvider.tsx`
- [x] T011 [P] Set up testing framework (Vitest + React Testing Library) in `frontend/src/test/setup.ts`
- [x] T012 Create Auth guard component in `frontend/src/components/auth/RequireAuth.tsx`
- [x] T013 Implement Dashboard layout with Sidebar and Header in `frontend/src/layouts/DashboardLayout.tsx`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - 基础认证与仪表盘 (Priority: P1) 🎯 MVP

**Goal**: 注册/登录后进入 Dashboard，支持明暗模式切换，查看统计概览。

**Independent Test**: 用户可以通过表单注册和登录，成功后跳转至包含统计卡片和上传区域的仪表盘。

### Implementation for User Story 1

- [x] T014 [US1] Create Login and Register split-screen page in `frontend/src/pages/Login.tsx`
- [x] T015 [US1] Implement Auth form logic with validation in `frontend/src/components/features/auth/AuthForm.tsx` (react-hook-form + zod)
- [x] T016 [P] [US1] Create Statistics card components in `frontend/src/components/features/dashboard/StatCard.tsx`
- [x] T017 [US1] Implement Dashboard page with statistics query in `frontend/src/pages/Dashboard.tsx`
- [x] T018 [P] [US1] Implement Theme provider and toggle in `frontend/src/components/common/ThemeToggle.tsx`
- [x] T019 [US1] Connect Logout action in `frontend/src/layouts/DashboardLayout.tsx`

**Checkpoint**: User Story 1 functional and testable independently.

---

## Phase 4: User Story 2 - 文献管理与 AI 处理 (Priority: P1)

**Goal**: 上传 PDF/Word 文献，并使用 AI 生成总结、进行问答和文本改写。

**Independent Test**: 上传一个文件，启动 AI 总结任务，并在 Workspace 中看到结果。

### Implementation for User Story 2

- [x] T020 [US2] Implement File and Task API services in `frontend/src/services/api.ts` (upload, list, summarize, qa, rewrite)
- [x] T021 [US2] Create Multi-file drag & drop upload component with large file/error handling in `frontend/src/components/features/files/FileUpload.tsx`
- [x] T022 [P] [US2] Create Document List data table in `frontend/src/pages/Documents.tsx` (shadcn DataTable)
- [x] T023 [US2] Create Workspace layout with resizable panels in `frontend/src/pages/Workspace.tsx`
- [x] T024 [P] [US2] Implement PDF Viewer with selection floating menu in `frontend/src/components/features/documents/PdfViewer.tsx`
- [x] T025 [P] [US2] Create Markdown renderer in `frontend/src/components/common/MarkdownRenderer.tsx`
- [x] T026 [US2] Implement Summary panel with auto-save and timeout logic in `frontend/src/components/features/documents/SummaryPanel.tsx`
- [x] T027 [US2] Implement AI Chat panel for Q&A with history auto-save in `frontend/src/components/features/documents/QAPanel.tsx`
- [x] T028 [US2] Implement Dual-column Rewrite panel with sync scroll and auto-save in `frontend/src/components/features/documents/RewritePanel.tsx`

**Checkpoint**: User Story 2 functional with document processing and AI tools.

---

## Phase 5: User Story 3 - 思维导图可视化 (Priority: P2)

**Goal**: 将文献结构可视化为 React Flow 思维导图，支持自动布局。

**Independent Test**: 在 Workspace 内切换至思维导图标签，触发生成并看到交互式节点图。

### Implementation for User Story 3

- [x] T029 [US3] Implement Mindmap API service in `frontend/src/services/mindmapService.ts`
- [x] T030 [P] [US3] Implement mindmap data transformation in `frontend/src/lib/mindmapUtils.ts`
- [x] T031 [P] [US3] Configure React Flow nodes and edges in `frontend/src/components/features/documents/mindmap/FlowContainer.tsx`
- [x] T032 [US3] Implement Mindmap panel with auto-layout in `frontend/src/components/features/documents/MindmapPanel.tsx`

**Checkpoint**: Mindmap visualization functional.

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T033 Implement WebSocket task listener in `frontend/src/hooks/useTaskWebSocket.ts` (connect to `/ws/tasks`)
- [x] T034 [P] Implement Task store for real-time updates in `frontend/src/stores/taskStore.ts`
- [x] T035 Implement Settings page for API Key and user preferences in `frontend/src/pages/Settings.tsx`
- [x] T036 [P] Implement global Toast notification system using shadcn/ui
- [x] T037 Add route-level page transitions in `frontend/src/App.tsx` (Framer Motion)
- [x] T038 Implement Playwright end-to-end tests for critical paths (US1, US2) in `frontend/e2e/`
- [x] T039 Verify performance targets (SC-001, SC-002, SC-004) using Lighthouse or custom benchmarks
- [x] T040 Perform final validation of `quickstart.md` scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on core user stories being complete

### Parallel Opportunities

- All Phase 1 tasks marked [P]
- Phase 2: T007, T008, T009, T010 can run in parallel
- US2: PDF Viewer (T023), Markdown (T024), and AI Panels (T025, T026, T027) can be implemented in parallel
- Polish: T033, T035 can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 & Document List)

1. Complete Phase 1 & 2
2. Complete US1 (Auth & Dashboard)
3. Complete US2 up to Document List and File Upload
4. **Checkpoint**: Basic app lifecycle complete

### Incremental Delivery

1. Add Workspace and AI Panels (Summary/QA)
2. Add Rewrite panel and Mindmap
3. Integrate WebSocket for real-time progress
