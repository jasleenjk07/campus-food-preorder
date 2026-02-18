from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from jose import JWTError, jwt #Used to decode and verify JWT

from app.auth.jwt import SECRET_KEY, ALGORITHM
from app.core.redis_ws import manager

router = APIRouter() #registers WebSocket route

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str
):
    user_id = await manager.connect(websocket, token)

    if not user_id:
        return

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)