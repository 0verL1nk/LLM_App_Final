// API 基础配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8501/api/v1';

// 请求拦截器
const request = async (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('auth_token');

  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(`${API_BASE_URL}${url}`, config);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || '请求失败');
  }

  return response.json();
};

// 认证相关 API
export const authAPI = {
  login: (username: string, password: string) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  register: (username: string, email: string, password: string) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    }),

  logout: () =>
    request('/auth/logout', { method: 'POST' }),

  getCurrentUser: () => request('/users/me'),
};

// 文件管理 API
export const filesAPI = {
  upload: (file: File, tags?: string[]) => {
    const formData = new FormData();
    formData.append('file', file);
    if (tags) {
      formData.append('tags', JSON.stringify(tags));
    }

    const token = localStorage.getItem('auth_token');
    return fetch(`${API_BASE_URL}/files/upload`, {
      method: 'POST',
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: formData,
    }).then((res) => res.json());
  },

  list: (params?: {
    page?: number;
    page_size?: number;
    search?: string;
    status?: string;
    sort?: string;
  }) => {
    const query = new URLSearchParams(params as any).toString();
    return request(`/files?${query}`);
  },

  get: (fileId: string) => request(`/files/${fileId}`),

  delete: (fileId: string) =>
    request(`/files/${fileId}`, { method: 'DELETE' }),
};

// 文档处理 API
export const documentsAPI = {
  extract: (fileId: string, taskId?: string) =>
    request(`/documents/${fileId}/extract`, {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId }),
    }),

  summarize: (fileId: string, options: any) =>
    request(`/documents/${fileId}/summarize`, {
      method: 'POST',
      body: JSON.stringify({ options }),
    }),

  qa: (fileId: string, question: string, context?: string, history?: any[]) =>
    request(`/documents/${fileId}/qa`, {
      method: 'POST',
      body: JSON.stringify({ question, context, history }),
    }),

  rewrite: (fileId: string, text: string, options: any) =>
    request(`/documents/${fileId}/rewrite`, {
      method: 'POST',
      body: JSON.stringify({ text, ...options }),
    }),

  mindmap: (fileId: string, options?: any) =>
    request(`/documents/${fileId}/mindmap`, {
      method: 'POST',
      body: JSON.stringify({ options }),
    }),
};

// 任务管理 API
export const tasksAPI = {
  get: (taskId: string) => request(`/tasks/${taskId}`),

  list: (params?: {
    status?: string;
    task_type?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams(params as any).toString();
    return request(`/tasks?${query}`);
  },

  cancel: (taskId: string) =>
    request(`/tasks/${taskId}/cancel`, { method: 'POST' }),
};

// 用户管理 API
export const usersAPI = {
  updateApiKey: (apiKey: string) =>
    request('/users/api-key', {
      method: 'PUT',
      body: JSON.stringify({ api_key: apiKey }),
    }),

  updatePreferences: (preferences: any) =>
    request('/users/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    }),
};

// 统计 API
export const statisticsAPI = {
  get: () => request('/statistics'),
};