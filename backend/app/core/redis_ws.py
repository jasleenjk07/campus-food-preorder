#This file replaces old in-memory WebSocket manager with a Redis-backed pub/sub system. Because: Old manager works only on 1 server instance, Redis manager ✅ works across multiple servers
import redis.asyncio as redis #Async Redis client
import asyncio #async tasks
import json #convert dict ↔ JSON string

from typing import Dict, List #store connections per user

from fastapi import WebSocket

from app.config import settings #loads .env variables
from app.auth.jwt import decode_access_token

class RedisConnectionManager: #WebSocket manager
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL) #Connects to Redis.
        self.active_connections: Dict[int, List[WebSocket]] = {}  # multiple connections per user

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
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("notifications")

        async for message in pubsub.listen(): #Listens for messages on all subscribed channels
            if message["type"] != "message": #Handle messages
                continue

            data = message["data"]

            if not data:
                continue
            
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            try:
                parsed_data = json.loads(data)
            except:
                continue
                
            user_id = parsed_data["user_id"]

            if user_id in self.active_connections:
                connections = self.active_connections[user_id]
                for websocket in list(connections):
                    try:
                        await websocket.send_json(parsed_data)
                    except Exception:
                        connections.remove(websocket)
                if not connections:
                    del self.active_connections[user_id]

manager = RedisConnectionManager()