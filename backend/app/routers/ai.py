from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging

from app.database import get_db
from app.models import AISettings, ConversationParticipant, Message
from app.services import AIService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Agent"])


# Pydantic schemas
class AISettingsCreate(BaseModel):
    model_config = {"protected_namespaces": ()}  # Allow model_name field

    ai_provider: str = "openai"  # 'openai' or 'anthropic'
    api_key: Optional[str] = None
    model_name: str = "gpt-4"
    system_prompt: Optional[str] = None
    response_tone: str = "professional"
    max_tokens: int = 500
    temperature: int = 7  # 0-10
    context_messages_count: int = 10


class AISettingsResponse(BaseModel):
    model_config = {"protected_namespaces": (), "from_attributes": True}  # Allow model_name field

    id: int
    user_id: int
    ai_provider: str
    model_name: str
    system_prompt: Optional[str]
    response_tone: str
    max_tokens: int
    temperature: int
    context_messages_count: int


class AIToggleRequest(BaseModel):
    ai_enabled: bool


class AITestRequest(BaseModel):
    conversation_id: str
    message: str


@router.post("/settings", response_model=AISettingsResponse)
async def create_or_update_ai_settings(
    settings: AISettingsCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Create or update AI settings for a user"""
    # Check if settings already exist
    existing_settings = db.query(AISettings).filter(
        AISettings.user_id == user_id
    ).first()

    if existing_settings:
        # Update existing settings
        for key, value in settings.dict().items():
            setattr(existing_settings, key, value)
        db.commit()
        db.refresh(existing_settings)
        return existing_settings
    else:
        # Create new settings
        db_settings = AISettings(
            user_id=user_id,
            **settings.dict()
        )
        db.add(db_settings)
        db.commit()
        db.refresh(db_settings)
        return db_settings


@router.get("/settings", response_model=AISettingsResponse)
async def get_ai_settings(
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get AI settings for a user"""
    settings = db.query(AISettings).filter(
        AISettings.user_id == user_id
    ).first()

    if not settings:
        # Return default settings if none exist
        raise HTTPException(status_code=404, detail="AI settings not found. Please create them first.")

    return settings


@router.post("/conversations/{conversation_id}/toggle")
async def toggle_ai_for_conversation(
    conversation_id: str,
    toggle: AIToggleRequest,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Toggle AI auto-response for a specific conversation"""
    # Find the conversation participant
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()

    if not participant:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Update AI enabled status
    participant.ai_enabled = toggle.ai_enabled
    db.commit()

    return {
        "conversation_id": conversation_id,
        "ai_enabled": participant.ai_enabled,
        "message": f"AI {'enabled' if participant.ai_enabled else 'disabled'} for this conversation"
    }


@router.get("/conversations/{conversation_id}/status")
async def get_ai_status_for_conversation(
    conversation_id: str,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get AI status for a specific conversation"""
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()

    if not participant:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation_id": conversation_id,
        "ai_enabled": participant.ai_enabled
    }


@router.post("/test")
async def test_ai_response(
    request: AITestRequest,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Test AI response without sending it to the actual conversation"""
    # Get AI settings
    ai_settings = db.query(AISettings).filter(
        AISettings.user_id == user_id
    ).first()

    if not ai_settings:
        raise HTTPException(
            status_code=404,
            detail="AI settings not found. Please configure your AI settings first."
        )

    if not ai_settings.api_key:
        raise HTTPException(
            status_code=400,
            detail="API key not configured. Please add your OpenAI or Anthropic API key in settings."
        )

    # Get conversation context
    recent_messages = db.query(Message).filter(
        Message.conversation_id == request.conversation_id
    ).order_by(Message.created_at.desc()).limit(
        ai_settings.context_messages_count
    ).all()

    # Reverse to get chronological order
    recent_messages = list(reversed(recent_messages))

    # Add the test message to context (simulate incoming message)
    test_messages = recent_messages.copy()

    # Get participant info for better context
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == request.conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()

    participant_name = "Customer"
    if participant:
        participant_name = participant.participant_name or participant.participant_username or "Customer"

    try:
        # Generate AI response
        ai_service = AIService()
        response_text = await ai_service.generate_response(
            ai_settings,
            test_messages,
            participant_name
        )

        if not response_text:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate AI response. Please check your API key and settings."
            )

        return {
            "response": response_text,
            "model_used": ai_settings.model_name,
            "provider": ai_settings.ai_provider,
            "context_messages": len(test_messages)
        }

    except Exception as e:
        logger.error(f"Error testing AI response: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate AI response: {str(e)}"
        )
