"""
AI Bot Service - Handles intelligent bot selection and response generation.

Implements hierarchical bot system:
1. Conversation Override Bot (manually assigned)
2. Funnel-Specific Bot (during funnel steps)
3. Workspace Default Bot (fallback)
"""

import httpx
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import (
    AIBot,
    ConversationAISettings,
    FunnelEnrollment,
    FunnelStep,
    Message,
    MessageDirection,
    ConnectedAccount,
)

logger = logging.getLogger(__name__)


class AIBotService:
    def __init__(self):
        self.openai_api_key = None  # Will be set from environment
        self.anthropic_api_key = None  # Will be set from environment

    async def get_active_bot_for_conversation(
        self,
        conversation_id: str,
        workspace_id: int,
        db: Session,
    ) -> Optional[AIBot]:
        """
        Determine which bot should respond based on hierarchical system.

        Priority:
        1. Conversation Override (manual assignment)
        2. Funnel Bot (if conversation is in funnel with ai_response step)
        3. Workspace Default Bot

        Returns:
            AIBot instance or None if no bot should respond
        """
        logger.info(f"🤖 Determining bot for conversation {conversation_id}")

        # 1. Check for conversation override
        conv_settings = (
            db.query(ConversationAISettings)
            .filter(
                ConversationAISettings.conversation_id == conversation_id,
                ConversationAISettings.workspace_id == workspace_id,
            )
            .first()
        )

        if conv_settings:
            # Check if AI is enabled for this conversation
            if not conv_settings.ai_enabled:
                logger.info("❌ AI disabled for this conversation")
                return None

            # Check for override bot
            if conv_settings.override_workspace_default and conv_settings.assigned_bot_id:
                bot = db.query(AIBot).filter(
                    AIBot.id == conv_settings.assigned_bot_id,
                    AIBot.is_active == True,
                ).first()
                if bot:
                    logger.info(f"✅ Using conversation override bot: {bot.name}")
                    return bot

        # 2. Check for active funnel with AI step
        active_enrollment = (
            db.query(FunnelEnrollment)
            .filter(
                FunnelEnrollment.conversation_id == conversation_id,
                FunnelEnrollment.status == "active",
            )
            .first()
        )

        if active_enrollment:
            # Get current step
            current_step = (
                db.query(FunnelStep)
                .filter(
                    FunnelStep.funnel_id == active_enrollment.funnel_id,
                    FunnelStep.step_order == active_enrollment.current_step,
                    FunnelStep.is_active == True,
                )
                .first()
            )

            if current_step and current_step.step_type == "ai_response":
                # Get bot from step config
                bot_id = current_step.step_config.get("bot_id")
                if bot_id:
                    bot = db.query(AIBot).filter(
                        AIBot.id == bot_id,
                        AIBot.is_active == True,
                    ).first()
                    if bot:
                        logger.info(f"✅ Using funnel bot: {bot.name}")
                        return bot

        # 3. Check for workspace default bot
        workspace_default = (
            db.query(AIBot)
            .filter(
                AIBot.workspace_id == workspace_id,
                AIBot.bot_type == "workspace_default",
                AIBot.is_active == True,
                AIBot.auto_respond == True,
            )
            .first()
        )

        if workspace_default:
            logger.info(f"✅ Using workspace default bot: {workspace_default.name}")
            return workspace_default

        logger.info("❌ No active bot found for this conversation")
        return None

    async def check_bot_triggers(
        self,
        bot: AIBot,
        message_text: str,
        db: Session,
    ) -> bool:
        """
        Check if bot's triggers match the incoming message.

        Returns:
            True if bot should respond, False otherwise
        """
        if not bot.triggers:
            # No triggers = always respond
            return True

        for trigger in bot.triggers:
            if not trigger.is_active:
                continue

            trigger_type = trigger.trigger_type
            config = trigger.trigger_config

            if trigger_type == "always":
                logger.info("✅ Trigger matched: always")
                return True

            elif trigger_type == "keyword":
                keywords = config.get("keywords", [])
                match_type = config.get("match", "any")  # any or all

                message_lower = message_text.lower()
                keyword_matches = [kw.lower() in message_lower for kw in keywords]

                if match_type == "any" and any(keyword_matches):
                    logger.info(f"✅ Trigger matched: keyword (any of {keywords})")
                    return True
                elif match_type == "all" and all(keyword_matches):
                    logger.info(f"✅ Trigger matched: keyword (all of {keywords})")
                    return True

            elif trigger_type == "time_based":
                # Check if current time is within configured hours
                # For simplicity, we'll implement basic time checking
                # TODO: Implement proper timezone-aware time checking
                pass

        logger.info("❌ No triggers matched")
        return False

    async def get_conversation_context(
        self,
        conversation_id: str,
        context_window: int,
        db: Session,
    ) -> List[Dict[str, str]]:
        """
        Get recent messages for conversation context.

        Returns:
            List of messages in OpenAI format: [{"role": "user", "content": "..."}]
        """
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(context_window)
            .all()
        )

        # Reverse to chronological order
        messages = list(reversed(messages))

        context = []
        for msg in messages:
            role = "assistant" if msg.direction == MessageDirection.OUTGOING else "user"
            content = msg.content or ""

            # Add attachment info if present
            if msg.attachment_url:
                content += f" [Attachment: {msg.attachment_type}]"

            context.append({"role": role, "content": content})

        return context

    async def check_message_limit(
        self,
        bot: AIBot,
        conversation_id: str,
        db: Session,
    ) -> bool:
        """
        Check if bot has reached its message limit for this conversation.

        Returns:
            True if bot can still respond, False if limit reached
        """
        if bot.max_messages_per_conversation is None:
            # No limit
            return True

        # Count bot messages in this conversation
        bot_message_count = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.direction == MessageDirection.OUTGOING,
                Message.content.contains(f"[Bot: {bot.name}]"),  # Tag bot messages
            )
            .count()
        )

        if bot_message_count >= bot.max_messages_per_conversation:
            logger.warning(
                f"⚠️ Bot {bot.name} has reached message limit ({bot.max_messages_per_conversation}) for conversation {conversation_id}"
            )
            return False

        return True

    async def generate_response(
        self,
        bot: AIBot,
        conversation_context: List[Dict[str, str]],
        user_message: str,
    ) -> Optional[str]:
        """
        Generate AI response using configured provider.

        Args:
            bot: AIBot instance with configuration
            conversation_context: Recent messages for context
            user_message: Latest user message

        Returns:
            Generated response text or None if error
        """
        try:
            if bot.ai_provider == "openai":
                return await self._generate_openai_response(bot, conversation_context, user_message)
            elif bot.ai_provider == "anthropic":
                return await self._generate_anthropic_response(bot, conversation_context, user_message)
            else:
                logger.error(f"Unsupported AI provider: {bot.ai_provider}")
                return None

        except Exception as e:
            logger.error(f"Error generating AI response: {e}", exc_info=True)
            return None

    async def _generate_openai_response(
        self,
        bot: AIBot,
        context: List[Dict[str, str]],
        user_message: str,
    ) -> Optional[str]:
        """Generate response using OpenAI API"""
        try:
            import os

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY not configured")
                return None

            # Build messages array
            messages = [{"role": "system", "content": bot.system_prompt}]
            messages.extend(context)
            messages.append({"role": "user", "content": user_message})

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": bot.ai_model,
                        "messages": messages,
                        "temperature": float(bot.temperature),
                        "max_tokens": bot.max_tokens,
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                    return None

                data = response.json()
                ai_response = data["choices"][0]["message"]["content"]

                logger.info(f"✅ Generated OpenAI response ({len(ai_response)} chars)")
                return ai_response

        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            return None

    async def _generate_anthropic_response(
        self,
        bot: AIBot,
        context: List[Dict[str, str]],
        user_message: str,
    ) -> Optional[str]:
        """Generate response using Anthropic API"""
        try:
            import os

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("ANTHROPIC_API_KEY not configured")
                return None

            # Build messages array (Anthropic format)
            messages = context.copy()
            messages.append({"role": "user", "content": user_message})

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": bot.ai_model,
                        "system": bot.system_prompt,
                        "messages": messages,
                        "temperature": float(bot.temperature),
                        "max_tokens": bot.max_tokens,
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(f"Anthropic API error: {response.status_code} - {response.text}")
                    return None

                data = response.json()
                ai_response = data["content"][0]["text"]

                logger.info(f"✅ Generated Anthropic response ({len(ai_response)} chars)")
                return ai_response

        except Exception as e:
            logger.error(f"Anthropic API error: {e}", exc_info=True)
            return None

    async def process_incoming_message(
        self,
        conversation_id: str,
        workspace_id: int,
        message_text: str,
        db: Session,
    ) -> Optional[str]:
        """
        Main entry point for AI bot processing.

        Returns:
            AI-generated response or None if bot shouldn't respond
        """
        try:
            logger.info(f"🤖 Processing message for AI bot: {conversation_id}")

            # 1. Get active bot
            bot = await self.get_active_bot_for_conversation(conversation_id, workspace_id, db)
            if not bot:
                return None

            # 2. Check triggers
            if not await self.check_bot_triggers(bot, message_text, db):
                return None

            # 3. Check message limit
            if not await self.check_message_limit(bot, conversation_id, db):
                logger.info("❌ Bot message limit reached")
                return None

            # 4. Apply response delay if configured
            if bot.response_delay_seconds > 0:
                import asyncio
                logger.info(f"⏳ Waiting {bot.response_delay_seconds}s before responding...")
                await asyncio.sleep(bot.response_delay_seconds)

            # 5. Get conversation context
            context = await self.get_conversation_context(
                conversation_id,
                bot.context_window_messages,
                db,
            )

            # 6. Generate response
            response = await self.generate_response(bot, context, message_text)

            if response:
                # Tag response with bot name for tracking
                tagged_response = f"{response}\n\n[Bot: {bot.name}]"
                logger.info(f"✅ AI bot response generated: {bot.name}")
                return tagged_response

            return None

        except Exception as e:
            logger.error(f"Error in AI bot processing: {e}", exc_info=True)
            return None
