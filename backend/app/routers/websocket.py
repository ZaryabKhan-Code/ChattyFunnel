from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
import logging
from app.websocket_manager import manager
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time messaging updates"""
    logger.info(f"🔌 WebSocket connection attempt for user {user_id}")

    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"❌ User {user_id} not found, rejecting WebSocket")
        await websocket.close(code=1008, reason="User not found")
        return

    logger.info(f"✅ User {user_id} verified, connecting WebSocket")
    await manager.connect(websocket, user_id)
    logger.info(f"✅ WebSocket connected for user {user_id}")

    try:
        # Keep connection alive and listen for messages
        while True:
            # Receive any messages from client (ping/pong, etc.)
            data = await websocket.receive_text()
            logger.info(f"📨 Received from user {user_id}: {data}")

            # Echo back or handle specific commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
                logger.info(f"🏓 Sent pong to user {user_id}")

    except WebSocketDisconnect:
        logger.info(f"🔌 User {user_id} disconnected from WebSocket")
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"❌ WebSocket error for user {user_id}: {e}", exc_info=True)
        manager.disconnect(websocket, user_id)
