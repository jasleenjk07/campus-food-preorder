#This file replaces old in-memory WebSocket manager with a Redis-backed pub/sub system. Because: Old manager works only on 1 server instance, Redis manager ✅ works across multiple servers
import redis.asyncio as redis
import asyncio
from typing import Dict, List
from fastapi import WebSocket

REDIS_URL = "redis://localhost:6379" #This connects to Redis running locally.

class RedisConnectionManager: #WebSocket manager
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.redis = redis.from_url(REDIS_URL) #Creates Redis connection
        self.pubsub = self.redis.pubsub() #Creates Redis PubSub object. This is used to: Subscribe to channels, Listen for messages


    async def connect(self, user_id: int, webSocket: WebSocket): #accepts user_id and WebSocket object, adds it to active_connections
        await webSocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = []

        self.active_connections[user_id].append(webSocket)

    def disconnect(self, user_id: int, websocket: WebSocket): #removes WebSocket from active_connections
        self.active_connections[user_id].remove(websocket)
        if not self.active_connections[user_id]:
            del self.active_connections[user_id]
    
    async def publish(self, user_id: int, message: str): #publishes message to Redis channel
        await self.redis.publish(f"user: {user_id}", message)

    async def start_listener(self):
        await self.pubsub.psubscribe("user:*") #Subscribes to all channels starting with "user:"

        async for message in self.pubsub.listen(): #Listens for messages on all subscribed channels
            if message["type"] == "pmessage": #Handle messages
                #Extract channel + data
                channel = message["channel"].decode()
                data = message["data"].decode()

                #Extract user_id from channel name
                user_id = int(channel.split(":")[1])

                #Send message to all connected WebSockets for this user
                if user_id in self.active_connections:
                    for ws in self.active_connections[user_id]:
                        await ws.send_text(data)