# Real-Time Messaging Implementation Guide

## Overview
This guide explains how to implement real-time messaging with:
- WebSocket for instant message updates
- Stable conversation IDs
- Sender name/info display
- Auto-refresh without manual sync

## Architecture

### 1. WebSocket Connection Flow
```
Frontend ←→ WebSocket ←→ Backend
    ↓                        ↓
 Real-time UI          Webhook Handler
                             ↓
                        Broadcast to User
```

### 2. Stable Conversation ID System

Instead of changing conversation IDs, we create a stable ID using:
```python
conversation_id = f"{platform}_{user_id}_{participant_id}"
```

This ensures the same conversation always has the same ID.

### 3. Components Created

1. **WebSocket Manager** (`websocket_manager.py`)
   - Manages active connections
   - Broadcasts messages to specific users

2. **Conversation Participants Model** (`conversation_participant.py`)
   - Stores participant info (name, username, profile pic)
   - Maps platform conversation IDs to stable IDs

3. **WebSocket Router** (`websocket.py`)
   - Handles WebSocket connections
   - Keeps connections alive

## Implementation Steps

### Backend Changes

#### 1. Update Webhook Handler

Add to `backend/app/routers/webhooks.py`:

```python
from app.websocket_manager import manager
from app.models import ConversationParticipant
import hashlib

async def handle_facebook_message(event: Dict[str, Any], db: Session):
    sender_id = event["sender"]["id"]
    recipient_id = event["recipient"]["id"]

    # Find the connected account
    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.platform == "facebook",
        ConnectedAccount.page_id == recipient_id,
        ConnectedAccount.is_active == True,
    ).first()

    if not account:
        return

    if "message" in event:
        message = event["message"]
        message_id = message.get("mid")
        message_text = message.get("text", "")

        # Create stable conversation ID
        conv_id = create_stable_conversation_id("facebook", account.user_id, sender_id)

        # Fetch sender information
        sender_info = await fetch_sender_info(sender_id, account.access_token, "facebook")

        # Update or create conversation participant
        participant = db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conv_id
        ).first()

        if not participant:
            participant = ConversationParticipant(
                conversation_id=conv_id,
                platform="facebook",
                platform_conversation_id=sender_id,
                participant_id=sender_id,
                participant_name=sender_info.get("name"),
                participant_username=sender_info.get("username"),
                participant_profile_pic=sender_info.get("profile_pic"),
                user_id=account.user_id,
            )
            db.add(participant)
        else:
            participant.participant_name = sender_info.get("name")
            participant.last_message_at = datetime.utcnow()

        # Save message
        db_message = Message(
            user_id=account.user_id,
            platform="facebook",
            conversation_id=conv_id,  # Use stable ID
            message_id=message_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            direction=MessageDirection.INCOMING,
            content=message_text,
            status=MessageStatus.DELIVERED,
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)

        # Broadcast to user via WebSocket
        await manager.broadcast_to_user(
            account.user_id,
            "new_message",
            {
                "conversation_id": conv_id,
                "message": {
                    "id": db_message.id,
                    "content": message_text,
                    "sender_id": sender_id,
                    "sender_name": sender_info.get("name"),
                    "created_at": db_message.created_at.isoformat(),
                    "direction": "incoming"
                }
            }
        )


def create_stable_conversation_id(platform: str, user_id: int, participant_id: str) -> str:
    """Create a stable conversation ID"""
    # Combine platform, user_id, and participant_id
    raw_id = f"{platform}_{user_id}_{participant_id}"
    # Create a hash for shorter ID
    return hashlib.md5(raw_id.encode()).hexdigest()[:16]


async def fetch_sender_info(sender_id: str, access_token: str, platform: str) -> dict:
    """Fetch sender information from Facebook/Instagram"""
    import httpx

    if platform == "facebook":
        url = f"https://graph.facebook.com/v18.0/{sender_id}"
        params = {
            "fields": "name,first_name,last_name,profile_pic",
            "access_token": access_token
        }
    else:  # Instagram
        url = f"https://graph.facebook.com/v18.0/{sender_id}"
        params = {
            "fields": "name,username,profile_picture_url",
            "access_token": access_token
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch sender info: {e}")

    return {"name": "Unknown", "username": sender_id}
```

#### 2. Update Message API

Update `backend/app/routers/messages.py` to use stable conversation IDs:

```python
@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    user_id: int = Query(...),
    platform: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all conversations with participant info"""
    query = db.query(ConversationParticipant).filter(
        ConversationParticipant.user_id == user_id
    )

    if platform:
        query = query.filter(ConversationParticipant.platform == platform)

    participants = query.order_by(ConversationParticipant.last_message_at.desc()).all()

    conversations = []
    for participant in participants:
        # Get last message
        last_message = db.query(Message).filter(
            Message.conversation_id == participant.conversation_id
        ).order_by(Message.created_at.desc()).first()

        conversations.append(ConversationResponse(
            conversation_id=participant.conversation_id,
            platform=participant.platform,
            participant_id=participant.participant_id,
            participant_name=participant.participant_name,
            last_message=last_message,
            unread_count=0  # TODO: Implement unread count
        ))

    return conversations
```

### Frontend Changes

#### 1. Create WebSocket Hook

Create `frontend/hooks/useWebSocket.ts`:

```typescript
import { useEffect, useRef, useState } from 'react'

export function useWebSocket(userId: number | null) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<any>(null)
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!userId) return

    // Connect to WebSocket
    const wsUrl = `${process.env.NEXT_PUBLIC_API_URL?.replace('http', 'ws')}/ws/${userId}`
    ws.current = new WebSocket(wsUrl)

    ws.current.onopen = () => {
      console.log('WebSocket connected')
      setIsConnected(true)

      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send('ping')
        }
      }, 30000)

      ws.current.pingInterval = pingInterval
    }

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data)
      console.log('WebSocket message:', data)
      setLastMessage(data)
    }

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.current.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
      if (ws.current?.pingInterval) {
        clearInterval(ws.current.pingInterval)
      }
    }

    // Cleanup
    return () => {
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [userId])

  return { isConnected, lastMessage }
}
```

#### 2. Update Messages Page

Update `frontend/app/messages/page.tsx`:

```typescript
import { useWebSocket } from '@/hooks/useWebSocket'

export default function Messages() {
  const [userId, setUserId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const { isConnected, lastMessage } = useWebSocket(userId)

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return

    if (lastMessage.type === 'new_message') {
      const { conversation_id, message } = lastMessage.data

      // If viewing this conversation, add message to list
      if (selectedConversation?.conversation_id === conversation_id) {
        setMessages(prev => [...prev, message])

        // Scroll to bottom
        setTimeout(() => {
          const messageContainer = document.getElementById('messages-container')
          if (messageContainer) {
            messageContainer.scrollTop = messageContainer.scrollHeight
          }
        }, 100)
      }

      // Update conversation list
      loadConversations()
    }
  }, [lastMessage])

  // ... rest of component
}
```

#### 3. Add Real-time Indicator

Add connection status indicator:

```typescript
{isConnected ? (
  <div className="flex items-center gap-2 text-green-600">
    <div className="w-2 h-2 bg-green-600 rounded-full animate-pulse" />
    <span className="text-sm">Live</span>
  </div>
) : (
  <div className="flex items-center gap-2 text-gray-400">
    <div className="w-2 h-2 bg-gray-400 rounded-full" />
    <span className="text-sm">Connecting...</span>
  </div>
)}
```

## Deployment

### Update Heroku

```bash
# Push changes
git push heroku main

# Run database migration to add new table
heroku run python -c "from app.database import init_db; init_db()"

# Check logs
heroku logs --tail
```

### Update Environment Variables

No new environment variables needed!

## Testing

1. **Connect WebSocket:**
   - Open browser console
   - Navigate to messages page
   - Check for "WebSocket connected" log

2. **Send Test Message:**
   - Message your Facebook Page
   - Should appear instantly in UI
   - No sync button needed!

3. **Verify Sender Info:**
   - Sender name should display
   - Conversation ID should stay same

## Benefits

✅ Instant message delivery (no manual sync)
✅ Consistent conversation IDs
✅ Sender names displayed
✅ Better user experience
✅ Scalable architecture

## Next Steps

1. Add typing indicators
2. Add read receipts
3. Add unread message count
4. Add message search
5. Add file attachments
