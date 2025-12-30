from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db
from app.models import (
    AIBot,
    AIBotTrigger,
    ConversationAISettings,
    WorkspaceMember,
)
from app.schemas.ai_bot import (
    AIBotCreate,
    AIBotUpdate,
    AIBotResponse,
    AIBotTriggerCreate,
    AIBotTriggerUpdate,
    AIBotTriggerResponse,
    ConversationAISettingsCreate,
    ConversationAISettingsUpdate,
    ConversationAISettingsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-bots", tags=["AI Bots"])


def verify_workspace_access(db: Session, workspace_id: int, user_id: int):
    """Verify user has access to workspace"""
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    return member


@router.post("", response_model=AIBotResponse)
async def create_ai_bot(
    bot: AIBotCreate,
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Create a new AI bot in a workspace"""
    # Verify access
    verify_workspace_access(db, workspace_id, user_id)

    try:
        # Create bot
        db_bot = AIBot(
            workspace_id=workspace_id,
            name=bot.name,
            bot_type=bot.bot_type,
            ai_provider=bot.ai_provider,
            ai_model=bot.ai_model,
            system_prompt=bot.system_prompt,
            temperature=bot.temperature,
            max_tokens=bot.max_tokens,
            auto_respond=bot.auto_respond,
            response_delay_seconds=bot.response_delay_seconds,
            max_messages_per_conversation=bot.max_messages_per_conversation,
            knowledge_base_url=bot.knowledge_base_url,
            context_window_messages=bot.context_window_messages,
            is_active=bot.is_active,
        )
        db.add(db_bot)
        db.flush()

        # Create triggers
        for trigger_data in bot.triggers:
            db_trigger = AIBotTrigger(
                bot_id=db_bot.id,
                trigger_type=trigger_data.trigger_type,
                trigger_config=trigger_data.trigger_config,
                priority=trigger_data.priority,
                is_active=trigger_data.is_active,
            )
            db.add(db_trigger)

        db.commit()
        db.refresh(db_bot)

        return AIBotResponse.model_validate(db_bot)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating AI bot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create AI bot: {str(e)}")


@router.get("", response_model=List[AIBotResponse])
async def list_ai_bots(
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    bot_type: str = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    """List all AI bots in a workspace"""
    # Verify access
    verify_workspace_access(db, workspace_id, user_id)

    query = db.query(AIBot).filter(AIBot.workspace_id == workspace_id)

    if bot_type:
        query = query.filter(AIBot.bot_type == bot_type)

    if not include_inactive:
        query = query.filter(AIBot.is_active == True)

    bots = query.order_by(AIBot.created_at.desc()).all()

    return [AIBotResponse.model_validate(bot) for bot in bots]


@router.get("/{bot_id}", response_model=AIBotResponse)
async def get_ai_bot(
    bot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get a specific AI bot"""
    bot = db.query(AIBot).filter(AIBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="AI bot not found")

    # Verify access
    verify_workspace_access(db, bot.workspace_id, user_id)

    return AIBotResponse.model_validate(bot)


@router.patch("/{bot_id}", response_model=AIBotResponse)
async def update_ai_bot(
    bot_id: int,
    bot_update: AIBotUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update an AI bot"""
    bot = db.query(AIBot).filter(AIBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="AI bot not found")

    # Verify access
    verify_workspace_access(db, bot.workspace_id, user_id)

    # Update fields
    update_data = bot_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bot, field, value)

    db.commit()
    db.refresh(bot)

    return AIBotResponse.model_validate(bot)


@router.delete("/{bot_id}")
async def delete_ai_bot(
    bot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Delete an AI bot"""
    bot = db.query(AIBot).filter(AIBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="AI bot not found")

    # Verify access
    verify_workspace_access(db, bot.workspace_id, user_id)

    db.delete(bot)
    db.commit()

    return {"message": "AI bot deleted successfully"}


# AI Bot Triggers Endpoints

@router.post("/{bot_id}/triggers", response_model=AIBotTriggerResponse)
async def create_bot_trigger(
    bot_id: int,
    trigger: AIBotTriggerCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Add a trigger to an AI bot"""
    bot = db.query(AIBot).filter(AIBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="AI bot not found")

    # Verify access
    verify_workspace_access(db, bot.workspace_id, user_id)

    # Create trigger
    db_trigger = AIBotTrigger(
        bot_id=bot_id,
        trigger_type=trigger.trigger_type,
        trigger_config=trigger.trigger_config,
        priority=trigger.priority,
        is_active=trigger.is_active,
    )
    db.add(db_trigger)
    db.commit()
    db.refresh(db_trigger)

    return AIBotTriggerResponse.model_validate(db_trigger)


@router.get("/{bot_id}/triggers", response_model=List[AIBotTriggerResponse])
async def list_bot_triggers(
    bot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """List all triggers for an AI bot"""
    bot = db.query(AIBot).filter(AIBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="AI bot not found")

    # Verify access
    verify_workspace_access(db, bot.workspace_id, user_id)

    triggers = (
        db.query(AIBotTrigger)
        .filter(AIBotTrigger.bot_id == bot_id)
        .order_by(AIBotTrigger.priority.desc())
        .all()
    )

    return [AIBotTriggerResponse.model_validate(trigger) for trigger in triggers]


@router.patch("/{bot_id}/triggers/{trigger_id}", response_model=AIBotTriggerResponse)
async def update_bot_trigger(
    bot_id: int,
    trigger_id: int,
    trigger_update: AIBotTriggerUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update a bot trigger"""
    bot = db.query(AIBot).filter(AIBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="AI bot not found")

    # Verify access
    verify_workspace_access(db, bot.workspace_id, user_id)

    trigger = (
        db.query(AIBotTrigger)
        .filter(
            AIBotTrigger.id == trigger_id,
            AIBotTrigger.bot_id == bot_id,
        )
        .first()
    )

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # Update fields
    update_data = trigger_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(trigger, field, value)

    db.commit()
    db.refresh(trigger)

    return AIBotTriggerResponse.model_validate(trigger)


@router.delete("/{bot_id}/triggers/{trigger_id}")
async def delete_bot_trigger(
    bot_id: int,
    trigger_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Delete a bot trigger"""
    bot = db.query(AIBot).filter(AIBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="AI bot not found")

    # Verify access
    verify_workspace_access(db, bot.workspace_id, user_id)

    trigger = (
        db.query(AIBotTrigger)
        .filter(
            AIBotTrigger.id == trigger_id,
            AIBotTrigger.bot_id == bot_id,
        )
        .first()
    )

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    db.delete(trigger)
    db.commit()

    return {"message": "Trigger deleted successfully"}


# Conversation AI Settings Endpoints

@router.post("/conversation-settings", response_model=ConversationAISettingsResponse)
async def create_conversation_ai_settings(
    settings: ConversationAISettingsCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Create or update AI settings for a conversation"""
    # Verify access
    verify_workspace_access(db, settings.workspace_id, user_id)

    # Check if settings already exist
    existing = (
        db.query(ConversationAISettings)
        .filter(ConversationAISettings.conversation_id == settings.conversation_id)
        .first()
    )

    if existing:
        # Update existing
        existing.ai_enabled = settings.ai_enabled
        existing.assigned_bot_id = settings.assigned_bot_id
        existing.override_workspace_default = settings.override_workspace_default
        db.commit()
        db.refresh(existing)
        return ConversationAISettingsResponse.model_validate(existing)

    # Create new settings
    db_settings = ConversationAISettings(
        conversation_id=settings.conversation_id,
        workspace_id=settings.workspace_id,
        ai_enabled=settings.ai_enabled,
        assigned_bot_id=settings.assigned_bot_id,
        override_workspace_default=settings.override_workspace_default,
    )
    db.add(db_settings)
    db.commit()
    db.refresh(db_settings)

    return ConversationAISettingsResponse.model_validate(db_settings)


@router.get("/conversation-settings/{conversation_id}", response_model=ConversationAISettingsResponse)
async def get_conversation_ai_settings(
    conversation_id: str,
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get AI settings for a conversation"""
    # Verify access
    verify_workspace_access(db, workspace_id, user_id)

    settings = (
        db.query(ConversationAISettings)
        .filter(
            ConversationAISettings.conversation_id == conversation_id,
            ConversationAISettings.workspace_id == workspace_id,
        )
        .first()
    )

    if not settings:
        # Return default settings
        return ConversationAISettingsResponse(
            id=0,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            ai_enabled=False,
            assigned_bot_id=None,
            funnel_id=None,
            override_workspace_default=False,
            created_at=None,
            updated_at=None,
        )

    return ConversationAISettingsResponse.model_validate(settings)


@router.patch("/conversation-settings/{conversation_id}", response_model=ConversationAISettingsResponse)
async def update_conversation_ai_settings(
    conversation_id: str,
    settings_update: ConversationAISettingsUpdate,
    workspace_id: int = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Update AI settings for a conversation"""
    # Verify access
    verify_workspace_access(db, workspace_id, user_id)

    settings = (
        db.query(ConversationAISettings)
        .filter(
            ConversationAISettings.conversation_id == conversation_id,
            ConversationAISettings.workspace_id == workspace_id,
        )
        .first()
    )

    if not settings:
        raise HTTPException(status_code=404, detail="Conversation AI settings not found")

    # Update fields
    update_data = settings_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    return ConversationAISettingsResponse.model_validate(settings)
