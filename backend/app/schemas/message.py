from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.models.message import MessageDirection, MessageStatus, MessageType


class MessageCreate(BaseModel):
    recipient_id: str
    content: Optional[str] = None  # Optional if sending attachment
    platform: str  # 'facebook' or 'instagram'
    attachment_url: Optional[str] = None  # URL of image, video, audio, or file
    attachment_type: Optional[str] = None  # MIME type (image/jpeg, video/mp4, audio/mpeg, etc.)


class MessageResponse(BaseModel):
    id: int
    platform: str
    conversation_id: str
    message_id: str
    sender_id: str
    recipient_id: str
    direction: MessageDirection
    message_type: MessageType
    content: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None
    attachment_filename: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: MessageStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    conversation_id: str
    platform: str
    participant_id: str
    participant_name: Optional[str] = None
    participant_username: Optional[str] = None
    participant_profile_pic: Optional[str] = None
    last_message: Optional[MessageResponse] = None
    unread_count: int = 0
    ai_enabled: bool = False


class WebhookMessage(BaseModel):
    sender_id: str
    recipient_id: str
    message_id: str
    message_text: str
    timestamp: int
