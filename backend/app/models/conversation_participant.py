from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship, deferred
from datetime import datetime
from app.database import Base


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), index=True, nullable=False)  # Our stable conversation ID
    platform = Column(String(50), nullable=False)  # 'facebook' or 'instagram'
    platform_conversation_id = Column(String(255), index=True)  # Original platform conversation ID
    participant_id = Column(String(255), nullable=False)  # Facebook/Instagram user ID
    participant_name = Column(String(255), nullable=True)
    participant_username = Column(String(255), nullable=True)
    participant_profile_pic = Column(String(500), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Workspace association - messages are scoped to workspaces
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)

    # AI Agent Configuration (nullable for backward compatibility before migration)
    ai_enabled = Column(Boolean, default=False, nullable=True)  # Toggle AI responses for this conversation

    # Conversation Assignment - which workspace member is assigned to handle this conversation
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)  # When the assignment was made

    last_message_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ConversationParticipant(conversation_id={self.conversation_id}, participant_name={self.participant_name})>"