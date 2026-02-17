#This file creates a secure WebSocket connection that: Accepts a JWT token, Verifies the token, Extracts the user_id, Connects only authenticated users, Sends them real-time notifications
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from jose import JWTError, jwt #Used to decode and verify JWT

from app.auth.jwt import SECRET_KEY, ALGORITHM
from app.core.redis_ws import manager

router = APIRouter() #registers WebSocket route

@router.websocket("/ws") 
async def websocket_endpoint( #When client connects like this: ws://localhost:8000/ws?token=YOUR_JWT
    websocket: WebSocket,
    token: str = Query(...)
):
    try:
        #Decode JWT
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id: int = payload.get("user_id")
        
        if user_id is None:
            await websocket.close()
            return
    
    except JWTError:
        await websocket.close()
        return

    await manager.connect(user_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)