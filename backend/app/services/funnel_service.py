"""
Funnel Service - Handles funnel execution and enrollment.

Executes funnel steps:
- send_message: Send automated message
- delay: Schedule next step execution
- condition: Branch based on user response
- tag: Add/remove conversation tags
- assign_human: Exit automation, notify human
- ai_response: Let AI bot respond
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models import (
    Funnel,
    FunnelStep,
    FunnelEnrollment,
    ConversationTag,
    ConversationAISettings,
)

logger = logging.getLogger(__name__)


class FunnelService:
    async def check_funnel_triggers(
        self,
        conversation_id: str,
        workspace_id: int,
        message_text: str,
        is_new_conversation: bool,
        db: Session,
    ) -> Optional[Funnel]:
        """
        Check if any funnel should be triggered for this message.

        Returns:
            Funnel instance if triggered, None otherwise
        """
        # Get all active funnels for workspace, ordered by priority
        funnels = (
            db.query(Funnel)
            .filter(
                Funnel.workspace_id == workspace_id,
                Funnel.is_active == True,
            )
            .order_by(Funnel.priority.desc())
            .all()
        )

        for funnel in funnels:
            if await self._check_trigger(funnel, conversation_id, message_text, is_new_conversation, db):
                logger.info(f"✅ Funnel triggered: {funnel.name}")
                return funnel

        return None

    async def _check_trigger(
        self,
        funnel: Funnel,
        conversation_id: str,
        message_text: str,
        is_new_conversation: bool,
        db: Session,
    ) -> bool:
        """Check if a specific funnel's trigger matches"""
        trigger_type = funnel.trigger_type
        config = funnel.trigger_config

        if trigger_type == "new_conversation":
            return is_new_conversation

        elif trigger_type == "keyword":
            keywords = config.get("keywords", [])
            match_type = config.get("match", "any")

            message_lower = message_text.lower()
            keyword_matches = [kw.lower() in message_lower for kw in keywords]

            if match_type == "any":
                return any(keyword_matches)
            elif match_type == "all":
                return all(keyword_matches)

        elif trigger_type == "tag":
            required_tags = config.get("tags", [])
            # Check if conversation has all required tags
            conv_tags = (
                db.query(ConversationTag)
                .filter(
                    ConversationTag.conversation_id == conversation_id,
                    ConversationTag.tag.in_(required_tags),
                )
                .all()
            )
            return len(conv_tags) >= len(required_tags)

        return False

    async def enroll_in_funnel(
        self,
        funnel_id: int,
        conversation_id: str,
        db: Session,
    ) -> Optional[FunnelEnrollment]:
        """
        Enroll a conversation in a funnel.

        Returns:
            FunnelEnrollment instance or None if already enrolled
        """
        # Check if already enrolled in active funnel
        existing = (
            db.query(FunnelEnrollment)
            .filter(
                FunnelEnrollment.funnel_id == funnel_id,
                FunnelEnrollment.conversation_id == conversation_id,
                FunnelEnrollment.status == "active",
            )
            .first()
        )

        if existing:
            logger.info(f"⚠️ Already enrolled in funnel {funnel_id}")
            return None

        # Create enrollment
        enrollment = FunnelEnrollment(
            funnel_id=funnel_id,
            conversation_id=conversation_id,
            current_step=1,
            status="active",
            enrolled_at=datetime.utcnow(),
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)

        logger.info(f"✅ Enrolled in funnel {funnel_id}: {conversation_id}")
        return enrollment

    async def execute_funnel_step(
        self,
        enrollment: FunnelEnrollment,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Execute the current step of a funnel enrollment.

        Returns:
            Dict with execution results:
            {
                "success": bool,
                "action": str,  # What was done
                "next_step_at": datetime or None,  # When to execute next step
                "message": str or None,  # Message to send (if step_type=send_message)
            }
        """
        # Get current step
        step = (
            db.query(FunnelStep)
            .filter(
                FunnelStep.funnel_id == enrollment.funnel_id,
                FunnelStep.step_order == enrollment.current_step,
                FunnelStep.is_active == True,
            )
            .first()
        )

        if not step:
            logger.error(f"Step {enrollment.current_step} not found for funnel {enrollment.funnel_id}")
            return {"success": False, "action": "error", "message": "Step not found"}

        logger.info(f"⚙️ Executing step {step.step_order}: {step.step_type}")

        result = {"success": True, "action": step.step_type}

        if step.step_type == "send_message":
            # Return message to send
            message_text = step.step_config.get("text", "")
            result["message"] = message_text
            result["next_step_at"] = datetime.utcnow()  # Execute next step immediately

        elif step.step_type == "delay":
            # Schedule next step
            delay_minutes = step.step_config.get("minutes", 0)
            delay_hours = step.step_config.get("hours", 0)
            delay_days = step.step_config.get("days", 0)

            total_delay = timedelta(
                days=delay_days,
                hours=delay_hours,
                minutes=delay_minutes,
            )

            next_step_at = datetime.utcnow() + total_delay
            result["next_step_at"] = next_step_at

            logger.info(f"⏳ Delay: next step at {next_step_at}")

        elif step.step_type == "condition":
            # Evaluate condition (simplified - just check if user replied)
            # TODO: Implement more complex condition logic
            condition_type = step.step_config.get("if", "user_replied")

            if condition_type == "user_replied":
                # This would be checked externally
                result["next_step_at"] = datetime.utcnow()

        elif step.step_type == "tag":
            # Add/remove tags
            tags_to_add = step.step_config.get("add", [])
            tags_to_remove = step.step_config.get("remove", [])

            # Add tags
            for tag in tags_to_add:
                existing = (
                    db.query(ConversationTag)
                    .filter(
                        ConversationTag.conversation_id == enrollment.conversation_id,
                        ConversationTag.tag == tag,
                    )
                    .first()
                )
                if not existing:
                    # Get workspace_id from funnel
                    funnel = db.query(Funnel).filter(Funnel.id == enrollment.funnel_id).first()
                    db_tag = ConversationTag(
                        workspace_id=funnel.workspace_id,
                        conversation_id=enrollment.conversation_id,
                        tag=tag,
                    )
                    db.add(db_tag)

            # Remove tags
            db.query(ConversationTag).filter(
                ConversationTag.conversation_id == enrollment.conversation_id,
                ConversationTag.tag.in_(tags_to_remove),
            ).delete(synchronize_session=False)

            db.commit()
            result["next_step_at"] = datetime.utcnow()
            logger.info(f"🏷️ Tags updated: +{tags_to_add}, -{tags_to_remove}")

        elif step.step_type == "assign_human":
            # Exit automation
            enrollment.status = "exited"
            enrollment.completed_at = datetime.utcnow()
            db.commit()

            result["action"] = "assign_human"
            result["next_step_at"] = None
            logger.info("👤 Assigned to human - funnel exited")

        elif step.step_type == "ai_response":
            # Enable AI for this conversation
            bot_id = step.step_config.get("bot_id")
            max_messages = step.step_config.get("max_messages")

            # Get or create conversation AI settings
            funnel = db.query(Funnel).filter(Funnel.id == enrollment.funnel_id).first()

            conv_settings = (
                db.query(ConversationAISettings)
                .filter(ConversationAISettings.conversation_id == enrollment.conversation_id)
                .first()
            )

            if conv_settings:
                conv_settings.ai_enabled = True
                conv_settings.funnel_id = enrollment.funnel_id
                if bot_id:
                    conv_settings.assigned_bot_id = bot_id
            else:
                conv_settings = ConversationAISettings(
                    conversation_id=enrollment.conversation_id,
                    workspace_id=funnel.workspace_id,
                    ai_enabled=True,
                    funnel_id=enrollment.funnel_id,
                    assigned_bot_id=bot_id,
                )
                db.add(conv_settings)

            db.commit()

            result["next_step_at"] = datetime.utcnow()
            logger.info(f"🤖 AI enabled with bot {bot_id}")

        # Update enrollment
        if result.get("next_step_at"):
            enrollment.next_step_at = result["next_step_at"]

            # Move to next step if executing now
            if result["next_step_at"] <= datetime.utcnow():
                enrollment.current_step += 1

                # Check if funnel is complete
                next_step_exists = (
                    db.query(FunnelStep)
                    .filter(
                        FunnelStep.funnel_id == enrollment.funnel_id,
                        FunnelStep.step_order == enrollment.current_step,
                    )
                    .first()
                )

                if not next_step_exists:
                    enrollment.status = "completed"
                    enrollment.completed_at = datetime.utcnow()
                    logger.info("✅ Funnel completed")

            db.commit()

        return result

    async def process_message_for_funnels(
        self,
        conversation_id: str,
        workspace_id: int,
        message_text: str,
        is_new_conversation: bool,
        db: Session,
    ) -> Optional[str]:
        """
        Main entry point for funnel processing.

        Returns:
            Message to send if funnel executed send_message step, None otherwise
        """
        try:
            logger.info(f"🔄 Checking funnels for conversation: {conversation_id}")

            # Check if conversation should trigger a funnel
            funnel = await self.check_funnel_triggers(
                conversation_id,
                workspace_id,
                message_text,
                is_new_conversation,
                db,
            )

            if funnel:
                # Enroll in funnel
                enrollment = await self.enroll_in_funnel(funnel.id, conversation_id, db)

                if enrollment:
                    # Execute first step
                    result = await self.execute_funnel_step(enrollment, db)

                    if result.get("success") and result.get("message"):
                        return result["message"]

            # Check for existing enrollments that need execution
            pending_enrollments = (
                db.query(FunnelEnrollment)
                .join(Funnel, FunnelEnrollment.funnel_id == Funnel.id)
                .filter(
                    FunnelEnrollment.conversation_id == conversation_id,
                    FunnelEnrollment.status == "active",
                    FunnelEnrollment.next_step_at <= datetime.utcnow(),
                    Funnel.workspace_id == workspace_id,
                )
                .all()
            )

            for enrollment in pending_enrollments:
                result = await self.execute_funnel_step(enrollment, db)
                if result.get("success") and result.get("message"):
                    return result["message"]

            return None

        except Exception as e:
            logger.error(f"Error in funnel processing: {e}", exc_info=True)
            return None
