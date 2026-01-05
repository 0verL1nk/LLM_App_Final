# Data Model: 现代前端重构 (Modern Frontend Refactor)

## Frontend Specific Entities

### 1. AuthState (Zustand)
- `isAuthenticated`: boolean
- `token`: string | null
- `user`: { id, username, email, apiKeyConfigured } | null

### 2. UIState (Zustand)
- `theme`: 'light' | 'dark' | 'system'
- `sidebarCollapsed`: boolean
- `activeWorkspaceFileId`: string | null
- `activeToolTab`: 'summary' | 'qa' | 'rewrite' | 'mindmap'

### 3. WorkspaceContext
- `currentFile`: FileDocument
- `currentTask`: AnalysisTask | null
- `chatHistory`: Array<ChatMessage>
- `mindmapNodes`: Array<ReactFlowNode>
- `mindmapEdges`: Array<ReactFlowEdge>

## API Entity Mapping (Matching Backend)

### FileItem
- `id`: string
- `filename`: string
- `status`: 'pending' | 'processing' | 'completed' | 'failed'
- `createdAt`: ISOString

### AnalysisTask
- `taskId`: string
- `type`: 'summarize' | 'qa' | 'rewrite' | 'mindmap'
- `status`: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
- `progress`: number (0-100)
- `result`: any
