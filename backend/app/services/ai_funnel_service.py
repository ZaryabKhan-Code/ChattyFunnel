"""
AI-Driven Funnel Movement Service

This service analyzes conversations using AI and automatically moves users
between different funnels based on conversation context.
"""

import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models import (
    Funnel,
    ConversationAISettings,
    Message,
    AIBot,
)

logger = logging.getLogger(__name__)


class AIFunnelService:
    """AI service that analyzes conversation and moves users between funnels"""

    async def analyze_and_move_funnel(
        self,
        conversation_id: str,
        workspace_id: int,
        message_text: str,
        db: Session,
    ) -> Optional[int]:
        """
        Analyze conversation and determine if user should be moved to different funnel.

        Returns:
            Funnel ID if user should be moved, None otherwise
        """
        try:
            # Get conversation settings
            conv_settings = (
                db.query(ConversationAISettings)
                .filter(
                    ConversationAISettings.conversation_id == conversation_id,
                    ConversationAISettings.workspace_id == workspace_id,
                )
                .first()
            )

            # Check if auto-funnel is enabled for this conversation
            if conv_settings and not conv_settings.auto_funnel_enabled:
                logger.info(f"🚫 Auto-funnel disabled for conversation {conversation_id}")
                return None

            # Get all available funnels in workspace
            available_funnels = (
                db.query(Funnel)
                .filter(
                    Funnel.workspace_id == workspace_id,
                    Funnel.is_active == True,
                )
                .all()
            )

            if not available_funnels:
                logger.info("No funnels available in workspace")
                return None

            # Get conversation history for context
            recent_messages = (
                db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(5)
                .all()
            )

            # Analyze message content and determine appropriate funnel
            selected_funnel = await self._ai_select_funnel(
                message_text=message_text,
                conversation_history=recent_messages,
                available_funnels=available_funnels,
                current_funnel_id=conv_settings.funnel_id if conv_settings else None,
            )

            if selected_funnel:
                # Update conversation settings with new funnel
                if not conv_settings:
                    conv_settings = ConversationAISettings(
                        conversation_id=conversation_id,
                        workspace_id=workspace_id,
                        ai_enabled=True,
                        funnel_id=selected_funnel.id,
                        auto_funnel_enabled=True,
                    )
                    db.add(conv_settings)
                else:
                    conv_settings.funnel_id = selected_funnel.id

                db.commit()
                logger.info(f"✅ Moved conversation to funnel: {selected_funnel.name}")
                return selected_funnel.id

            return None

        except Exception as e:
            logger.error(f"Error in AI funnel analysis: {e}", exc_info=True)
            return None

    async def _ai_select_funnel(
        self,
        message_text: str,
        conversation_history: List[Message],
        available_funnels: List[Funnel],
        current_funnel_id: Optional[int],
    ) -> Optional[Funnel]:
        """
        Use AI to analyze conversation and select appropriate funnel.

        Simple keyword-based matching for now. Can be enhanced with actual AI later.
        """
        message_lower = message_text.lower()

        # Define funnel selection rules based on keywords
        funnel_keywords = {
            "pricing": ["pricing", "price", "cost", "how much", "payment", "subscription"],
            "support": ["help", "problem", "issue", "broken", "not working", "error", "bug"],
            "demo": ["demo", "show me", "trial", "test", "preview"],
            "sales": ["buy", "purchase", "interested", "want to get", "sign up"],
            "onboarding": ["new", "getting started", "how to", "tutorial", "guide"],
        }

        # Score each funnel based on keyword matches
        funnel_scores = {}
        for funnel in available_funnels:
            score = 0
            funnel_name_lower = funnel.name.lower()

            # Match funnel name to keywords
            for category, keywords in funnel_keywords.items():
                if category in funnel_name_lower:
                    # Check if message contains related keywords
                    for keyword in keywords:
                        if keyword in message_lower:
                            score += 10
                            break

            # Bonus for exact keyword match in funnel name
            for word in message_lower.split():
                if len(word) > 3 and word in funnel_name_lower:
                    score += 5

            if score > 0:
                funnel_scores[funnel.id] = score

        # Select highest scoring funnel (if score > 0)
        if funnel_scores:
            best_funnel_id = max(funnel_scores, key=funnel_scores.get)
            best_funnel = next(f for f in available_funnels if f.id == best_funnel_id)

            # Don't move if already in the best funnel
            if best_funnel_id == current_funnel_id:
                logger.info(f"Already in best funnel: {best_funnel.name}")
                return None

            logger.info(f"AI selected funnel: {best_funnel.name} (score: {funnel_scores[best_funnel_id]})")
            return best_funnel

        return None

    async def toggle_auto_funnel(
        self,
        conversation_id: str,
        workspace_id: int,
        enabled: bool,
        db: Session,
    ) -> bool:
        """Toggle auto-funnel movement for a specific conversation"""
        try:
            conv_settings = (
                db.query(ConversationAISettings)
                .filter(
                    ConversationAISettings.conversation_id == conversation_id,
                    ConversationAISettings.workspace_id == workspace_id,
                )
                .first()
            )

            if not conv_settings:
                conv_settings = ConversationAISettings(
                    conversation_id=conversation_id,
                    workspace_id=workspace_id,
                    ai_enabled=True,
                    auto_funnel_enabled=enabled,
                )
                db.add(conv_settings)
            else:
                conv_settings.auto_funnel_enabled = enabled

            db.commit()
            logger.info(f"✅ Auto-funnel {'enabled' if enabled else 'disabled'} for {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to toggle auto-funnel: {e}")
            return False
