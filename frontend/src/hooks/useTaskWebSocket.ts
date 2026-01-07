import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useTaskStore } from '@/stores/taskStore';
import type { AnalysisTask } from '@/types';

const WS_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8501/api/v1/ws/tasks';

export function useTaskWebSocket() {
  const token = useAuthStore((state) => state.token);
  const setTask = useTaskStore((state) => state.setTask);
  const updateTask = useTaskStore((state) => state.updateTask);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;

  const connect = useCallback(() => {
    if (!token || socketRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const socket = new WebSocket(`${WS_URL}?token=${token}`);
      socketRef.current = socket;

      socket.onopen = () => {
        console.log('WebSocket connected successfully');
        reconnectAttemptsRef.current = 0; // Reset reconnect attempts on successful connection
      };

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

      socket.onclose = (event) => {
        console.log(`WebSocket closed: ${event.code} ${event.reason}`);

        // Only reconnect if it wasn't intentionally closed and we haven't exceeded max attempts
        if (event.code !== 1000 && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1;
          const delay = Math.min(5000 * Math.pow(2, reconnectAttemptsRef.current - 1), 30000); // Exponential backoff, max 30s

          console.log(`WebSocket reconnecting in ${delay}ms... (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          console.warn('WebSocket max reconnect attempts reached. Stopping reconnection.');
        }
      };

      socket.onerror = (event) => {
        console.error('WebSocket error observed:', event);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [token, setTask, updateTask]);

  useEffect(() => {
    connect();

    return () => {
      // Clear any pending reconnect timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }

      // Close the WebSocket connection
      if (socketRef.current) {
        socketRef.current.close(1000, 'Component unmounted');
      }
    };
  }, [connect]);

  return {
    isConnected: socketRef.current?.readyState === WebSocket.OPEN
  };
}
