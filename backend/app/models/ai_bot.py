from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class AIBot(Base):
    __tablename__ = "ai_bots"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    bot_type = Column(String(50), nullable=False)  # workspace_default, funnel_specific, conversation_override

    # Bot configuration
    ai_provider = Column(String(50), default="openai")  # openai, anthropic, custom
    ai_model = Column(String(100), default="gpt-4")
    system_prompt = Column(Text, nullable=False)
    temperature = Column(DECIMAL(3, 2), default=0.7)
    max_tokens = Column(Integer, default=500)

    # Behavior settings
    auto_respond = Column(Boolean, default=False)
    response_delay_seconds = Column(Integer, default=0)
    max_messages_per_conversation = Column(Integer, nullable=True)  # NULL = unlimited

    # Training data
    knowledge_base_url = Column(Text, nullable=True)
    context_window_messages = Column(Integer, default=10)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    workspace = relationship("Workspace", back_populates="ai_bots")
    triggers = relationship("AIBotTrigger", back_populates="bot", cascade="all, delete-orphan")
    conversation_settings = relationship("ConversationAISettings", back_populates="assigned_bot")


class AIBotTrigger(Base):
    __tablename__ = "ai_bot_triggers"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("ai_bots.id", ondelete="CASCADE"), nullable=False)
    trigger_type = Column(String(50), nullable=False)  # keyword, sentiment, time_based, always
    trigger_config = Column(JSON, nullable=False, default={})
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Relationships
    bot = relationship("AIBot", back_populates="triggers")


class ConversationAISettings(Base):
    __tablename__ = "conversation_ai_settings"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), nullable=False, unique=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    ai_enabled = Column(Boolean, default=False)
    assigned_bot_id = Column(Integer, ForeignKey("ai_bots.id", ondelete="SET NULL"), nullable=True)
    funnel_id = Column(Integer, ForeignKey("funnels.id", ondelete="SET NULL"), nullable=True)  # Current funnel
    override_workspace_default = Column(Boolean, default=False)
    auto_funnel_enabled = Column(Boolean, default=True)  # Allow AI to move user between funnels
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assigned_bot = relationship("AIBot", back_populates="conversation_settings")
    funnel = relationship("Funnel")
