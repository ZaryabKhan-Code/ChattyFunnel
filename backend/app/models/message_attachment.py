from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    attachment_type = Column(String(50), nullable=False)  # image, video, audio, voice_note, file
    file_url = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)  # bytes
    mime_type = Column(String(100), nullable=True)
    duration = Column(Integer, nullable=True)  # For audio/video in seconds

    # Voice note specific
    is_voice_note = Column(Boolean, default=False)
    transcription = Column(Text, nullable=True)  # AI transcription (not used for now)

    # Storage metadata
    storage_provider = Column(String(50), default="local")  # local, s3, cloudinary
    storage_path = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="attachments")
