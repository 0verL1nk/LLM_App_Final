// 用户类型
export interface User {
  user_id: string;
  username: string;
  email: string;
  api_key_configured?: boolean;
  preferred_model?: string;
  created_at: string;
  updated_at: string;
}

// 文件类型
export interface FileItem {
  file_id: string;
  original_filename: string;
  filename: string;
  file_size: number;
  mime_type: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  tags?: string[];
  upload_url?: string;
  created_at: string;
  updated_at?: string;
  extracted_text?: string;
  word_count?: number;
}

// 任务类型
export interface Task {
  task_id: string;
  task_type: 'extract' | 'summarize' | 'qa' | 'rewrite' | 'mindmap';
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  result?: any;
  file?: {
    file_id: string;
    filename: string;
  };
}

// 文档总结类型
export interface DocumentSummary {
  summary: string;
  key_points: string[];
  sections_summary: {
    section: string;
    summary: string;
  }[];
  statistics: {
    original_length: number;
    summary_length: number;
    compression_ratio: number;
  };
}

// 问答类型
export interface QAResult {
  answer: string;
  confidence: number;
  sources: {
    page: number;
    section: string;
    excerpt: string;
  }[];
  suggested_questions: string[];
}

// 改写类型
export interface RewriteResult {
  rewritten_text: string;
  original_length: number;
  rewritten_length: number;
  improvements: string[];
  alternatives: {
    text: string;
    description: string;
  }[];
}

// 思维导图类型
export interface MindMapNode {
  name: string;
  value?: number;
  children?: MindMapNode[];
}

export interface MindMapResult {
  mindmap: {
    name: string;
    children: MindMapNode[];
  };
  keywords: string[];
  structure: {
    total_branches: number;
    max_depth: number;
    main_topics: string[];
  };
}

// 统计类型
export interface Statistics {
  files: {
    total: number;
    processed: number;
    processing: number;
    this_month: number;
  };
  usage: {
    total_api_calls: number;
    total_tokens: number;
    this_month_calls: number;
  };
  tasks: {
    total_completed: number;
    pending: number;
    average_completion_time: number;
  };
}

// API 响应类型
export interface ApiResponse<T = any> {
  success: boolean;
  data: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

// 分页类型
export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  pagination: Pagination;
}

// 文件上传响应类型
export interface FileUploadResponse {
  file_id: string;
  original_filename: string;
  filename: string;
  file_size: number;
  mime_type: string;
  md5: string;
  upload_url: string;
  processing_status: string;
  created_at: string;
}