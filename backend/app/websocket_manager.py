#Which users are connected via WebSocket and sends notifications instantly to them.
from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager: #This class stores active WebSocket connections, sends messages to specific users, handles connect & disconnect
    def __init__(self):
        # user_id -> list of active websocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}
    #{
    #1: [WebSocket1, WebSocket2],
    #5: [WebSocket3],
    #}

    #Why List? Because a user can have multiple WebSocket connections. Mobile + Web at same time
    async def connect(self, user_id: int, websocket: WebSocket): #This method accepts a WebSocket connection and adds it to the active connections for the user
        await websocket.accept() #Accepts the WebSocket connection without this connection is rejected
        if user_id not in self.active_connections: #If user connects for the first time: Create empty list for them
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket) #Add this WebSocket to their list.

    def disconnect(self, user_id: int, websocket: WebSocket): #When user closes browser / internet drops:
        self.active_connections[user_id].remove(websocket) #Remove that specific WebSocket.
        if not self.active_connections[user_id]: #If user has no active connections left: Remove them from dictionary.
            del self.active_connections[user_id]

    async def send_notification(self, user_id: int, message: str):
        if user_id in self.active_connections: #Only send if user is online.
            for connection in self.active_connections[user_id]:
                await connection.send_text(message) #Send real-time message to user.