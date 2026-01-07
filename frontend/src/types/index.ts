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
  file_id: string;
  original_filename: string;
  filename: string;
  file_size: number;
  mime_type: string;
  processing_status: FileStatus;
  is_favorite: boolean;
  tags?: string[];
  created_at: string;
  updated_at: string;
  extracted_text?: string;
  word_count?: number;
  md5?: string;
  // Legacy fields for backward compatibility
  id?: string;
  status?: FileStatus;
  createdAt?: string;
  isFavorite?: boolean;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
