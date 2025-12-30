from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# AI Bot Trigger Schemas
class AIBotTriggerBase(BaseModel):
    trigger_type: str  # keyword, sentiment, time_based, always
    trigger_config: Dict[str, Any] = {}
    priority: int = 0
    is_active: bool = True


class AIBotTriggerCreate(AIBotTriggerBase):
    pass


class AIBotTriggerUpdate(BaseModel):
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class AIBotTriggerResponse(AIBotTriggerBase):
    id: int
    bot_id: int

    class Config:
        from_attributes = True


# AI Bot Schemas
class AIBotBase(BaseModel):
    name: str
    bot_type: str  # workspace_default, funnel_specific, conversation_override
    ai_provider: str = "openai"  # openai, anthropic, custom
    ai_model: str = "gpt-4"
    system_prompt: str
    temperature: Optional[Decimal] = Decimal("0.7")
    max_tokens: int = 500
    auto_respond: bool = False
    response_delay_seconds: int = 0
    max_messages_per_conversation: Optional[int] = None
    knowledge_base_url: Optional[str] = None
    context_window_messages: int = 10
    is_active: bool = True


class AIBotCreate(AIBotBase):
    triggers: List[AIBotTriggerCreate] = []


class AIBotUpdate(BaseModel):
    name: Optional[str] = None
    bot_type: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[Decimal] = None
    max_tokens: Optional[int] = None
    auto_respond: Optional[bool] = None
    response_delay_seconds: Optional[int] = None
    max_messages_per_conversation: Optional[int] = None
    knowledge_base_url: Optional[str] = None
    context_window_messages: Optional[int] = None
    is_active: Optional[bool] = None


class AIBotResponse(AIBotBase):
    id: int
    workspace_id: int
    created_at: datetime
    updated_at: datetime
    triggers: List[AIBotTriggerResponse] = []

    class Config:
        from_attributes = True


# Conversation AI Settings Schemas
class ConversationAISettingsCreate(BaseModel):
    conversation_id: str
    workspace_id: int
    ai_enabled: bool = False
    assigned_bot_id: Optional[int] = None
    override_workspace_default: bool = False


class ConversationAISettingsUpdate(BaseModel):
    ai_enabled: Optional[bool] = None
    assigned_bot_id: Optional[int] = None
    override_workspace_default: Optional[bool] = None


class ConversationAISettingsResponse(BaseModel):
    id: int
    conversation_id: str
    workspace_id: int
    ai_enabled: bool
    assigned_bot_id: Optional[int] = None
    funnel_id: Optional[int] = None
    override_workspace_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
