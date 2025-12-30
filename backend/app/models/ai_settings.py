from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class AISettings(Base):
    __tablename__ = "ai_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # AI Provider Configuration
    ai_provider = Column(String(50), default="openai", nullable=False)  # 'openai' or 'anthropic'
    api_key = Column(String(500), nullable=True)  # Encrypted in production
    model_name = Column(String(100), default="gpt-4", nullable=False)  # e.g., 'gpt-4', 'claude-3-sonnet'

    # AI Personality & Instructions
    system_prompt = Column(Text, nullable=True)  # Custom system prompt/personality
    response_tone = Column(String(50), default="professional", nullable=False)  # professional, friendly, casual
    max_tokens = Column(Integer, default=500, nullable=False)  # Max response length
    temperature = Column(Integer, default=7, nullable=False)  # 0-10, controls randomness (stored as int, divide by 10)

    # Conversation Context
    context_messages_count = Column(Integer, default=10, nullable=False)  # Number of previous messages to include

    # User relationship
    user = relationship("User", back_populates="ai_settings")

    def __repr__(self):
        return f"<AISettings(user_id={self.user_id}, provider={self.ai_provider})>"
