"""
WebSocket endpoint for real-time task status updates.
"""

import asyncio
from typing import Dict, Set
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from llm_app.api.deps import get_db
from llm_app.services.task_service import TaskService
from llm_app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_uuid: str) -> None:
        await websocket.accept()
        if user_uuid not in self.active_connections:
            self.active_connections[user_uuid] = set()
        self.active_connections[user_uuid].add(websocket)
        logger.info(f"WebSocket connected for user {user_uuid}")

    def disconnect(self, websocket: WebSocket, user_uuid: str) -> None:
        if user_uuid in self.active_connections:
            self.active_connections[user_uuid].discard(websocket)
            if not self.active_connections[user_uuid]:
                del self.active_connections[user_uuid]
        logger.info(f"WebSocket disconnected for user {user_uuid}")

    async def send_to_user(self, user_uuid: str, message: dict) -> None:
        if user_uuid in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[user_uuid]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)
            for conn in dead_connections:
                self.active_connections[user_uuid].discard(conn)

    async def broadcast_task_update(
        self, user_uuid: str, task_id: str, status: str, progress: int
    ) -> None:
        await self.send_to_user(
            user_uuid,
            {
                "type": "task_update",
                "data": {
                    "task_id": task_id,
                    "status": status,
                    "progress": progress,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
        )


manager = ConnectionManager()


@router.websocket("/ws/tasks")
async def websocket_tasks(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
):
    """WebSocket endpoint for task status updates"""
    from llm_app.core.security import verify_token

    try:
        payload = verify_token(token)
        user_uuid = payload.get("sub")
        if not user_uuid:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await manager.connect(websocket, user_uuid)

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            elif data.get("type") == "subscribe_task":
                task_id = data.get("task_id")
                if task_id:
                    await websocket.send_json(
                        {
                            "type": "subscribed",
                            "data": {"task_id": task_id},
                        }
                    )

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_uuid)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, user_uuid)


async def notify_task_update(
    user_uuid: str, task_id: str, status: str, progress: int
) -> None:
    """Utility function to notify clients of task updates"""
    await manager.broadcast_task_update(user_uuid, task_id, status, progress)
