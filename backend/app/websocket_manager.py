from typing import Dict, List
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Store active WebSocket connections per user
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept and store a WebSocket connection for a user"""
        logger.info(f"🔌 CONNECT called for user {user_id}")
        logger.info(f"🔌 Accepting WebSocket...")
        await websocket.accept()
        logger.info(f"🔌 WebSocket accepted")
        logger.info(f"🔌 Current active_connections keys: {list(self.active_connections.keys())}")

        if user_id not in self.active_connections:
            logger.info(f"🔌 Creating new connection list for user {user_id}")
            self.active_connections[user_id] = []

        logger.info(f"🔌 Appending websocket to user {user_id} connections")
        self.active_connections[user_id].append(websocket)
        logger.info(f"✅ WebSocket connected for user {user_id}. Total connections: {len(self.active_connections[user_id])}")
        logger.info(f"🔌 All active connections: {[(uid, len(conns)) for uid, conns in self.active_connections.items()]}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if len(self.active_connections[user_id]) == 0:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to a specific user's all connections"""
        if user_id in self.active_connections:
            logger.info(f"📨 Sending message to {len(self.active_connections[user_id])} connection(s) for user {user_id}")
            disconnected = []
            sent_count = 0
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                    sent_count += 1
                    logger.info(f"✅ Message sent successfully to connection #{sent_count}")
                except Exception as e:
                    logger.error(f"❌ Error sending message to user {user_id}: {e}")
                    disconnected.append(connection)

            # Clean up disconnected connections
            for conn in disconnected:
                self.disconnect(conn, user_id)

            logger.info(f"📊 Total sent: {sent_count}/{len(self.active_connections[user_id])}, Disconnected: {len(disconnected)}")
        else:
            logger.warning(f"⚠️  No active connections for user {user_id} - message not sent!")

    async def broadcast_to_user(self, user_id: int, event_type: str, data: dict):
        """Broadcast an event to all connections of a specific user"""
        message = {
            "type": event_type,
            "data": data
        }

        logger.info(f"🔔 broadcast_to_user called for user {user_id}, event: {event_type}")
        logger.info(f"🔔 Active connections for user {user_id}: {len(self.active_connections.get(user_id, []))}")
        logger.info(f"🔔 Message payload: {message}")

        await self.send_personal_message(message, user_id)

        logger.info(f"🔔 broadcast_to_user completed for user {user_id}")


# Global connection manager instance
manager = ConnectionManager()
