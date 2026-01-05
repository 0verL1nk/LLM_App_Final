import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useTaskStore } from '@/stores/taskStore';
import type { AnalysisTask } from '@/types';

const WS_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/api/v1/ws/tasks';

export function useTaskWebSocket() {
  const token = useAuthStore((state) => state.token);
  const setTask = useTaskStore((state) => state.setTask);
  const updateTask = useTaskStore((state) => state.updateTask);
  const socketRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!token || socketRef.current?.readyState === WebSocket.OPEN) return;

    const socket = new WebSocket(`${WS_URL}?token=${token}`);
    socketRef.current = socket;

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'task_update') {
          const task: AnalysisTask = data.task;
          setTask(task);
        } else if (data.type === 'task_progress') {
          updateTask(data.taskId, { progress: data.progress, status: data.status });
        }
      } catch (err) {
        console.error('WebSocket message error:', err);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket closed, retrying in 5s...');
      setTimeout(connect, 5000);
    };

    socket.onerror = (err) => {
      console.error('WebSocket error:', err);
      socket.close();
    };
  }, [token, setTask, updateTask]);

  useEffect(() => {
    connect();
    return () => {
      socketRef.current?.close();
    };
  }, [connect]);

  return {
    isConnected: socketRef.current?.readyState === WebSocket.OPEN
  };
}
