import { http } from './http';
import type { FileDocument, AnalysisTask, ChatMessage } from '@/types';

export const authService = {
  login: (data: any) => http.post<any>('/auth/login', data),
  register: (data: any) => http.post<any>('/auth/register', data),
  logout: () => http.post<any>('/auth/logout'),
};

export const fileService = {
  getFiles: (params?: any) => http.get<FileDocument[]>('/files/', { params }),
  getFile: (id: string) => http.get<FileDocument>(`/files/${id}`),
  uploadFile: (formData: FormData) => http.post<FileDocument>('/files/upload', formData),
  deleteFile: (id: string) => http.delete<any>(`/files/${id}`),
};

export const documentService = {
  summarize: (id: string, options?: any) => http.post<AnalysisTask>(`/documents/${id}/summarize`, options),
  qa: (id: string, question: string, history: ChatMessage[]) => 
    http.post<AnalysisTask>(`/documents/${id}/qa`, { question, history }),
  rewrite: (id: string, text: string, style: string) => 
    http.post<AnalysisTask>(`/documents/${id}/rewrite`, { text, style }),
  getMindmap: (id: string) => http.post<any>(`/documents/${id}/mindmap`),
};

export const taskService = {
  getTasks: () => http.get<AnalysisTask[]>('/tasks/'),
  getTask: (id: string) => http.get<AnalysisTask>(`/tasks/${id}`),
  cancelTask: (id: string) => http.post<any>(`/tasks/${id}/cancel`),
};

export const userService = {
  getMe: () => http.get<any>('/users/me'),
  updateApiKey: (apiKey: string) => http.put<any>('/users/api-key', { apiKey }),
  updatePreferences: (preferences: any) => http.put<any>('/users/preferences', preferences),
};
