import { http } from './http';
import type { AnalysisTask, ChatMessage } from '@/types';

export const authService = {
  login: (data: any) => http.post<any>('/auth/login', data),
  register: (data: any) => http.post<any>('/auth/register', data),
  logout: () => http.post<any>('/auth/logout'),
};

export const fileService = {
  getFiles: (params?: any) => http.get<any>('/files', { params }),
  getFile: (id: string) => http.get<any>(`/files/${id}`),
  uploadFile: (formData: FormData) => http.post<any>('/files/upload', formData),
  deleteFile: (id: string) => http.delete<any>(`/files/${id}`),
  getFavorites: (params?: any) => http.get<any>('/files/favorites', { params }),
  toggleFavorite: (id: string) => http.patch<any>(`/files/${id}/favorite`),
  setFavorite: (id: string, isFavorite: boolean) => http.put<any>(`/files/${id}/favorite`, { isFavorite }),
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
  getTasks: () => http.get<AnalysisTask[]>('/tasks'),
  getTask: (id: string) => http.get<AnalysisTask>(`/tasks/${id}`),
  cancelTask: (id: string) => http.post<any>(`/tasks/${id}/cancel`),
};

export const userService = {
  getMe: () => http.get<any>('/users/me'),
  updateApiKey: (apiKey: string) => http.put<any>('/users/api-key', { apiKey }),
  deleteApiKey: () => http.delete<any>('/users/api-key'),
  updatePreferences: (preferences: any) => http.put<any>('/users/preferences', preferences),
};

export const statisticsService = {
  getSummary: () => http.get<any>('/statistics/summary'),
  getFileStats: () => http.get<any>('/statistics/files'),
  getTaskStats: () => http.get<any>('/statistics/tasks'),
};
