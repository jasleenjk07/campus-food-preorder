import asyncio
import json
import logging
from typing import Dict, List

import redis.asyncio as redis
from fastapi import WebSocket

from app.config import settings
from app.auth.jwt import decode_access_token

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    def __init__(self):
        self.redis = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, token: str):
        await websocket.accept()

        try:
            payload = decode_access_token(token)
            user_id = payload.get("user_id")
            if not user_id:
                await websocket.close(code=1008)
                return None
        except Exception:
            await websocket.close(code=1008)
            return None

        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        return user_id

    def disconnect(self, websocket: WebSocket):
        for user_id, connections in list(self.active_connections.items()):
            if websocket in connections:
                connections.remove(websocket)
                if not connections:
                    del self.active_connections[user_id]
                break

    async def start_listener(self):
        """Background Redis pub/sub listener with reconnect."""
        while True:
            try:
                pubsub = self.redis.pubsub()
                await asyncio.wait_for(pubsub.subscribe("notifications"), timeout=5)
                logger.info("Redis websocket listener subscribed")

                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue

                    data = message.get("data")
                    if not data:
                        continue
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    try:
                        parsed_data = json.loads(data)
                    except Exception:
                        continue

                    user_id = parsed_data.get("user_id")
                    if user_id is None:
                        continue

                    connections = self.active_connections.get(user_id) or []
                    for websocket in list(connections):
                        try:
                            await websocket.send_json(parsed_data)
                        except Exception:
                            try:
                                connections.remove(websocket)
                            except ValueError:
                                pass
                    if user_id in self.active_connections and not self.active_connections[user_id]:
                        del self.active_connections[user_id]

            except Exception as exc:
                logger.warning("Redis websocket listener error: %s", exc)
                await asyncio.sleep(3)

    async def publish(self, user_id: int, data: dict):
        payload = {**data, "user_id": user_id}
        await self.redis.publish("notifications", json.dumps(payload))


manager = RedisConnectionManager()
