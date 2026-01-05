export interface User {
  id: string;
  username: string;
  email: string;
  apiKeyConfigured: boolean;
}

export interface AuthState {
  isAuthenticated: boolean;
  token: string | null;
  user: User | null;
}

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
export type TaskType = 'summarize' | 'qa' | 'rewrite' | 'mindmap';

export interface AnalysisTask {
  taskId: string;
  type: TaskType;
  status: TaskStatus;
  progress: number;
  result?: any;
}

export type FileStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface FileDocument {
  id: string;
  filename: string;
  status: FileStatus;
  createdAt: string;
  summary?: string;
  extractedText?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
