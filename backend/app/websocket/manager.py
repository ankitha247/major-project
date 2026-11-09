import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionInfo:
    def __init__(self, websocket: WebSocket, user_id: str, session_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.session_id = session_id
        self.connected_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()


class WebSocketManager:
    def __init__(self):
        self._interview_connections: dict[str, ConnectionInfo] = {}
        self._emotion_connections: dict[str, ConnectionInfo] = {}
        self._lock = asyncio.Lock()

    async def connect_interview(
        self, websocket: WebSocket, user_id: str, session_id: str
    ) -> None:
        await websocket.accept()
        async with self._lock:
            if session_id in self._interview_connections:
                old = self._interview_connections[session_id]
                try:
                    await old.websocket.close(code=1001)
                except Exception:
                    pass
            self._interview_connections[session_id] = ConnectionInfo(
                websocket, user_id, session_id
            )
        logger.info("Interview WS connected: session=%s user=%s", session_id, user_id)

    async def disconnect_interview(self, session_id: str) -> None:
        async with self._lock:
            self._interview_connections.pop(session_id, None)
        logger.info("Interview WS disconnected: session=%s", session_id)

    async def connect_emotion(
        self, websocket: WebSocket, user_id: str, session_id: str
    ) -> None:
        await websocket.accept()
        async with self._lock:
            if session_id in self._emotion_connections:
                old = self._emotion_connections[session_id]
                try:
                    await old.websocket.close(code=1001)
                except Exception:
                    pass
            self._emotion_connections[session_id] = ConnectionInfo(
                websocket, user_id, session_id
            )
        logger.info("Emotion WS connected: session=%s user=%s", session_id, user_id)

    async def disconnect_emotion(self, session_id: str) -> None:
        async with self._lock:
            self._emotion_connections.pop(session_id, None)
        logger.info("Emotion WS disconnected: session=%s", session_id)

    async def send_to_interview(self, session_id: str, payload: dict) -> bool:
        conn = self._interview_connections.get(session_id)
        if not conn:
            return False
        try:
            await conn.websocket.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError) as exc:
            logger.warning("Failed to send interview msg to %s: %s", session_id, exc)
            await self.disconnect_interview(session_id)
            return False

    async def send_to_emotion(self, session_id: str, payload: dict) -> bool:
        conn = self._emotion_connections.get(session_id)
        if not conn:
            return False
        try:
            await conn.websocket.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError) as exc:
            logger.warning("Failed to send emotion msg to %s: %s", session_id, exc)
            await self.disconnect_emotion(session_id)
            return False

    async def ping(self, session_id: str) -> bool:
        conn = self._interview_connections.get(session_id)
        if not conn:
            return False
        try:
            await conn.websocket.send_json(
                {"type": "ping", "ts": datetime.utcnow().isoformat()}
            )
            conn.last_ping = datetime.utcnow()
            return True
        except Exception:
            await self.disconnect_interview(session_id)
            return False

    def is_interview_connected(self, session_id: str) -> bool:
        return session_id in self._interview_connections

    def is_emotion_connected(self, session_id: str) -> bool:
        return session_id in self._emotion_connections

    @property
    def active_interview_count(self) -> int:
        return len(self._interview_connections)

    @property
    def active_emotion_count(self) -> int:
        return len(self._emotion_connections)


# Singleton — import this everywhere
ws_manager = WebSocketManager()