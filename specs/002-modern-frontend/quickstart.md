# Quickstart: 现代前端重构 (Modern Frontend Refactor)

## 环境要求
- Node.js 18+
- pnpm (推荐)
- 后端 API: `http://localhost:8501` (需运行 `uvicorn main:app`)

## 快速开始

1. **进入目录**:
   ```bash
   cd frontend
   ```

2. **安装依赖**:
   ```bash
   pnpm install
   ```

3. **初始化 shadcn/ui**:
   ```bash
   npx shadcn@latest init
   ```

4. **安装核心组件**:
   ```bash
   npx shadcn@latest add button card tabs scroll-area input form
   ```

5. **启动开发服务**:
   ```bash
   pnpm dev
   ```

## 关键文件
- `src/stores/authStore.ts`: 认证状态管理
- `src/hooks/useWebSocket.ts`: 任务进度监听
- `src/pages/Workspace.tsx`: 核心沉浸式阅读页面
