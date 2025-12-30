from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MessageAttachmentCreate(BaseModel):
    attachment_type: str  # image, video, audio, voice_note, file
    file_url: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    duration: Optional[int] = None
    is_voice_note: bool = False
    storage_provider: str = "local"
    storage_path: Optional[str] = None


class MessageAttachmentResponse(MessageAttachmentCreate):
    id: int
    message_id: int
    transcription: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AttachmentUploadResponse(BaseModel):
    file_url: str
    file_name: str
    file_size: int
    mime_type: str
    storage_path: str
