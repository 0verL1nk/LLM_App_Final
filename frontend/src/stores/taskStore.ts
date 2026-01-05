import { create } from 'zustand';
import type { AnalysisTask } from '@/types';

interface TaskState {
  tasks: Record<string, AnalysisTask>;
  setTask: (task: AnalysisTask) => void;
  updateTask: (taskId: string, updates: Partial<AnalysisTask>) => void;
  removeTask: (taskId: string) => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: {},
  setTask: (task) => set((state) => ({
    tasks: { ...state.tasks, [task.taskId]: task }
  })),
  updateTask: (taskId, updates) => set((state) => {
    const task = state.tasks[taskId];
    if (!task) return state;
    return {
      tasks: { ...state.tasks, [taskId]: { ...task, ...updates } }
    };
  }),
  removeTask: (taskId) => set((state) => {
    const next = { ...state.tasks };
    delete next[taskId];
    return { tasks: next };
  }),
}));
