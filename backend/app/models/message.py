from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class MessageDirection(str, enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class MessageStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    STICKER = "sticker"
    LOCATION = "location"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    platform = Column(String(50), nullable=False)  # 'facebook' or 'instagram'
    conversation_id = Column(String(255), nullable=False, index=True)
    message_id = Column(String(255), unique=True, index=True)  # Platform's message ID
    sender_id = Column(String(255), nullable=False)
    recipient_id = Column(String(255), nullable=False)
    direction = Column(Enum(MessageDirection), nullable=False)
    message_type = Column(Enum(MessageType), default=MessageType.TEXT, nullable=False)
    content = Column(Text, nullable=True)  # Nullable for media-only messages

    # Media attachment fields
    attachment_url = Column(String(500), nullable=True)  # URL to the media file
    attachment_type = Column(String(50), nullable=True)  # MIME type (image/jpeg, video/mp4, etc.)
    attachment_filename = Column(String(255), nullable=True)  # Original filename
    thumbnail_url = Column(String(500), nullable=True)  # Thumbnail for videos/images

    status = Column(Enum(MessageStatus), default=MessageStatus.SENT)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="messages")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Message(platform={self.platform}, direction={self.direction})>"