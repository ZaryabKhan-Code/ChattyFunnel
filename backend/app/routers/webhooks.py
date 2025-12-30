from fastapi import APIRouter, Request, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import hmac
import hashlib
import httpx
import logging
from datetime import datetime

from app.database import get_db, SessionLocal
from app.models import Message, ConnectedAccount, MessageDirection, MessageStatus, MessageType, ConversationParticipant, AISettings, Workspace
from app.config import settings
from app.websocket_manager import manager
from app.services import FacebookService, InstagramService, AIService
from app.services.ai_bot_service import AIBotService
from app.services.funnel_service import FunnelService
from app.services.ai_funnel_service import AIFunnelService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def create_stable_conversation_id(platform: str, user_id: int, participant_id: str) -> str:
    """Create a stable conversation ID that doesn't change"""
    raw_id = f"{platform}_{user_id}_{participant_id}"
    # Create a hash for consistent ID
    return hashlib.md5(raw_id.encode()).hexdigest()[:16]


async def fetch_sender_info(sender_id: str, access_token: str, platform: str) -> dict:
    """Fetch sender information from Facebook/Instagram API"""
    import logging
    logger = logging.getLogger(__name__)

    if platform == "facebook":
        url = f"https://graph.facebook.com/v18.0/{sender_id}"
        params = {
            "fields": "name,first_name,last_name,profile_pic",
            "access_token": access_token
        }
    else:  # Instagram
        # Detect token type and use appropriate endpoint
        if access_token.startswith("IGAAL"):
            # Instagram Business Login token - use graph.instagram.com
            url = f"https://graph.instagram.com/{sender_id}"
            logger.info("🔑 Using Instagram Business Login endpoint for sender info")
            # Per Instagram User Profile API, we can get profile_pic for users who messaged us
            # Available fields: name, username, profile_pic, follower_count, is_user_follow_business, is_business_follow_user
            params = {
                "fields": "name,username,profile_pic",
                "access_token": access_token
            }
        else:
            # Facebook token - use graph.facebook.com
            url = f"https://graph.facebook.com/v18.0/{sender_id}"
            logger.info("🔑 Using Facebook Graph API endpoint for sender info")
            # Facebook Page-linked Instagram can access profile_picture_url
            params = {
                "fields": "id,name,username,profile_picture_url",
                "access_token": access_token
            }

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"👤 Fetching {platform} sender info for {sender_id}")
            logger.info(f"👤 Request: GET {url}?fields={params['fields']}")

            response = await client.get(url, params=params)

            logger.info(f"👤 Response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"👤 Sender data received: {data}")

                # Extract available fields - Instagram uses profile_picture_url, Facebook uses profile_pic
                profile_pic = data.get("profile_pic") or data.get("profile_picture_url")
                result = {
                    "name": data.get("name") or data.get("username") or "User",
                    "username": data.get("username") or data.get("first_name") or sender_id,
                    "profile_pic": profile_pic
                }
                logger.info(f"👤 Parsed sender info: {result}")
                return result
            else:
                logger.warning(f"👤 Failed to fetch sender info: {response.status_code}")
                try:
                    error_data = response.json()
                    logger.warning(f"👤 Error response: {error_data}")
                except:
                    logger.warning(f"👤 Response text: {response.text}")
    except Exception as e:
        logger.error(f"👤 Failed to fetch sender info for {sender_id}: {e}", exc_info=True)

    # Return None values if fetch fails - caller should use fallback data
    # Don't use sender_id as username - it's confusing to users
    return {"name": None, "username": None, "profile_pic": None}


def parse_message_attachments(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse attachments from Facebook/Instagram message"""
    attachments = message.get("attachments", [])
    if not attachments:
        return None

    attachment = attachments[0]  # Get first attachment
    attachment_type = attachment.get("type")
    payload = attachment.get("payload", {})

    result = {
        "type": attachment_type,
        "url": payload.get("url"),
    }

    # Map Facebook attachment types to our MessageType
    type_mapping = {
        "image": MessageType.IMAGE,
        "video": MessageType.VIDEO,
        "audio": MessageType.AUDIO,
        "file": MessageType.FILE,
    }
    result["message_type"] = type_mapping.get(attachment_type, MessageType.FILE)

    # Get MIME type if available
    if "content_type" in payload:
        result["content_type"] = payload["content_type"]

    # Get filename if available
    if "name" in payload:
        result["filename"] = payload["name"]

    return result


async def trigger_ai_response(
    db: Session,
    account: ConnectedAccount,
    participant: ConversationParticipant,
    conv_id: str,
    sender_id: str,
    platform: str
):
    """Generate and send AI response for a conversation"""
    logger.info("=" * 60)
    logger.info(f"🤖 TRIGGERING AI RESPONSE")
    logger.info(f"Conversation: {conv_id}")
    logger.info(f"User: {account.user_id}")
    logger.info(f"Platform: {platform}")
    logger.info("=" * 60)

    try:
        # Get AI settings for the user
        logger.info(f"Fetching AI settings for user {account.user_id}...")
        ai_settings = db.query(AISettings).filter(
            AISettings.user_id == account.user_id
        ).first()

        if not ai_settings:
            logger.warning(f"❌ AI enabled for conversation {conv_id} but no AI settings found for user {account.user_id}")
            logger.warning(f"💡 User needs to configure AI settings in the AI Settings page")
            return

        logger.info(f"✅ Found AI settings:")
        logger.info(f"   Provider: {ai_settings.ai_provider}")
        logger.info(f"   Model: {ai_settings.model_name}")
        logger.info(f"   Has API key: {bool(ai_settings.api_key)}")

        if not ai_settings.api_key:
            logger.warning(f"❌ AI settings exist but API key is not configured")
            logger.warning(f"💡 User needs to add API key in AI Settings page")
            return

        # Get recent conversation history
        logger.info(f"Fetching last {ai_settings.context_messages_count} messages for context...")
        recent_messages = db.query(Message).filter(
            Message.conversation_id == conv_id
        ).order_by(Message.created_at.desc()).limit(
            ai_settings.context_messages_count
        ).all()

        # Reverse to get chronological order
        recent_messages = list(reversed(recent_messages))
        logger.info(f"✅ Found {len(recent_messages)} messages for context")

        # Generate AI response
        logger.info(f"Generating AI response using {ai_settings.ai_provider} {ai_settings.model_name}...")
        ai_service = AIService()
        response_text = await ai_service.generate_response(
            ai_settings,
            recent_messages,
            participant.participant_name or "User"
        )

        if not response_text:
            logger.error(f"❌ Failed to generate AI response for conversation {conv_id}")
            return

        logger.info(f"✅ Generated AI response ({len(response_text)} chars): {response_text[:100]}...")

        # Send the response via the appropriate platform
        logger.info(f"Sending AI response via {platform}...")
        if platform == "facebook":
            fb_service = FacebookService()
            result = await fb_service.send_message(
                recipient_id=sender_id,
                message_text=response_text,
                page_access_token=account.access_token
            )
            message_id = result.get("message_id")
            logger.info(f"✅ Sent Facebook message: {message_id}")
        elif platform == "instagram":
            ig_service = InstagramService()
            # Instagram requires page_id for sending messages
            if not account.page_id:
                logger.error(f"❌ Instagram account {account.id} missing page_id")
                return

            result = await ig_service.send_message(
                recipient_id=sender_id,
                message_text=response_text,
                access_token=account.access_token,
                page_id=account.page_id
            )
            message_id = result.get("message_id")
            logger.info(f"✅ Sent Instagram message: {message_id}")
        else:
            logger.error(f"❌ Unknown platform: {platform}")
            return

        # Save AI response to database
        ai_message = Message(
            user_id=account.user_id,
            platform=platform,
            conversation_id=conv_id,
            message_id=message_id,
            sender_id=account.page_id if platform == "facebook" else account.platform_user_id,
            recipient_id=sender_id,
            direction=MessageDirection.OUTGOING,
            message_type=MessageType.TEXT,
            content=response_text,
            status=MessageStatus.SENT,
        )
        db.add(ai_message)
        db.commit()
        db.refresh(ai_message)

        # Broadcast AI response via WebSocket
        await manager.broadcast_to_user(
            account.user_id,
            "new_message",
            {
                "conversation_id": conv_id,
                "message": {
                    "id": ai_message.id,
                    "content": response_text,
                    "sender_id": ai_message.sender_id,
                    "sender_name": "AI Assistant",
                    "message_type": MessageType.TEXT.value,
                    "attachment_url": None,
                    "created_at": ai_message.created_at.isoformat(),
                    "direction": "outgoing"
                }
            }
        )

        logger.info(f"✅✅✅ AI response sent successfully for conversation {conv_id}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌❌❌ Error in trigger_ai_response: {e}", exc_info=True)
        logger.error("=" * 60)


def verify_facebook_signature(payload: bytes, signature: str) -> bool:
    """Verify the Facebook webhook signature"""
    expected_signature = hmac.new(
        settings.FACEBOOK_APP_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected_signature}", signature)


def verify_instagram_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Instagram webhook signature.
    Supports both:
    - Instagram Business Login (uses INSTAGRAM_APP_SECRET)
    - Facebook Page-managed Instagram (uses FACEBOOK_APP_SECRET)
    """
    # Try Instagram Business Login secret first
    instagram_signature = hmac.new(
        settings.INSTAGRAM_APP_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if hmac.compare_digest(f"sha256={instagram_signature}", signature):
        logger.info("✅ Verified with Instagram Business Login secret")
        return True

    # Try Facebook Page-managed Instagram secret
    facebook_signature = hmac.new(
        settings.FACEBOOK_APP_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if hmac.compare_digest(f"sha256={facebook_signature}", signature):
        logger.info("✅ Verified with Facebook App secret (Page-managed Instagram)")
        return True

    logger.error("❌ Signature verification failed with both secrets")
    return False


@router.get("/facebook")
async def verify_facebook_webhook(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Verify Facebook webhook subscription"""
    # Get verify token from environment variable
    VERIFY_TOKEN = getattr(settings, 'WEBHOOK_VERIFY_TOKEN', 'my_secure_verify_token_12345')

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    else:
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/facebook")
async def facebook_webhook(request: Request):
    """Handle Facebook webhook events"""
    logger.info("=" * 80)
    logger.info("FACEBOOK WEBHOOK RECEIVED")
    logger.info("=" * 80)

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    payload = await request.body()

    logger.info(f"Signature: {signature[:50]}...")
    logger.info(f"Payload size: {len(payload)} bytes")

    if not verify_facebook_signature(payload, signature):
        logger.error("WEBHOOK SIGNATURE VERIFICATION FAILED!")
        raise HTTPException(status_code=403, detail="Invalid signature")

    logger.info("Signature verified successfully")

    # Process webhook
    data = await request.json()
    logger.info(f"Webhook data: {data}")

    db = SessionLocal()
    try:
        # Handle webhook entries
        entries = data.get("entry", [])
        logger.info(f"Processing {len(entries)} webhook entries")

        for entry in entries:
            logger.info(f"Entry: {entry.get('id')}")
            # Handle messaging events
            messaging_events = entry.get("messaging", [])
            logger.info(f"Found {len(messaging_events)} messaging events")

            for messaging_event in messaging_events:
                logger.info(f"Processing messaging event: {messaging_event}")
                await handle_facebook_message(messaging_event, db)

        logger.info("✅ All webhook events processed successfully")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}", exc_info=True)
        raise
    finally:
        db.close()


async def handle_facebook_message(event: Dict[str, Any], db: Session):
    """Process a Facebook Messenger message event"""
    logger.info(f"🔵 Processing Facebook message event: {event.keys()}")

    sender_id = event.get("sender", {}).get("id")
    recipient_id = event.get("recipient", {}).get("id")

    logger.info(f"Sender ID: {sender_id}, Recipient ID: {recipient_id}")

    # Get message
    if "message" in event:
        message = event["message"]
        message_id = message.get("mid")
        message_text = message.get("text", "")
        is_echo = message.get("is_echo", False)

        logger.info(f"Message ID: {message_id}")
        logger.info(f"Message text: {message_text}")
        logger.info(f"Is echo: {is_echo}")

        # For echo messages, sender is the page, recipient is the user
        # For regular messages, sender is the user, recipient is the page
        if is_echo:
            page_id = sender_id
            user_psid = recipient_id
            direction = MessageDirection.OUTGOING
            logger.info(f"Processing echo message (sent by page {page_id} to user {user_psid})")
        else:
            page_id = recipient_id
            user_psid = sender_id
            direction = MessageDirection.INCOMING
            logger.info(f"Processing incoming message (from user {user_psid} to page {page_id})")

        # Find the connected account using page_id
        # IMPORTANT: Only process for ACTIVE accounts in ACTIVE workspaces
        logger.info(f"Looking for connected account with page_id: {page_id}")
        account = (
            db.query(ConnectedAccount)
            .join(Workspace, ConnectedAccount.workspace_id == Workspace.id)
            .filter(
                ConnectedAccount.platform == "facebook",
                ConnectedAccount.page_id == page_id,
                ConnectedAccount.is_active == True,
                Workspace.is_active == True,
            )
            .first()
        )

        # IMPORTANT: Check if there's an INACTIVE account for this page_id
        # If found, we should REJECT the webhook - don't process at all
        if not account:
            inactive_account = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.platform == "facebook",
                    ConnectedAccount.page_id == page_id,
                )
                .first()
            )
            if inactive_account:
                workspace = db.query(Workspace).filter(Workspace.id == inactive_account.workspace_id).first()
                if not inactive_account.is_active:
                    logger.warning(f"🚫 REJECTING webhook: Facebook account for page {page_id} is INACTIVE (is_active=False)")
                    logger.warning(f"🚫 Account ID: {inactive_account.id}, Page: {inactive_account.page_name}")
                    return  # Reject the webhook
                if workspace and not workspace.is_active:
                    logger.warning(f"🚫 REJECTING webhook: Facebook account's workspace is INACTIVE (workspace.is_active=False)")
                    logger.warning(f"🚫 Account ID: {inactive_account.id}, Workspace ID: {workspace.id}")
                    return  # Reject the webhook

        if account:
            logger.info(f"✅ Found connected account: {account.id} (user: {account.user_id})")
            # Check if message already exists
            existing = (
                db.query(Message).filter(Message.message_id == message_id).first()
            )

            if existing:
                logger.info(f"⏭️  Message {message_id} already exists in database, skipping")
                return

            if not existing:
                logger.info(f"💾 Saving new Facebook message to database (direction: {direction})")
                # Create stable conversation ID using the user's PSID (not the page)
                conv_id = create_stable_conversation_id("facebook", account.user_id, user_psid)

                # Fetch user information (the person chatting with the page)
                user_info = await fetch_sender_info(user_psid, account.access_token, "facebook")

                # Update or create conversation participant
                # IMPORTANT: Filter by workspace_id to allow same conversation in multiple workspaces
                participant = db.query(ConversationParticipant).filter(
                    ConversationParticipant.conversation_id == conv_id,
                    ConversationParticipant.workspace_id == account.workspace_id
                ).first()

                if not participant:
                    participant = ConversationParticipant(
                        conversation_id=conv_id,
                        platform="facebook",
                        platform_conversation_id=user_psid,
                        participant_id=user_psid,
                        participant_name=user_info.get("name"),
                        participant_username=user_info.get("username"),
                        participant_profile_pic=user_info.get("profile_pic"),
                        user_id=account.user_id,
                        workspace_id=account.workspace_id,
                        last_message_at=datetime.utcnow(),
                    )
                    db.add(participant)
                else:
                    # Update participant info and last message time
                    if user_info.get("name"):
                        participant.participant_name = user_info.get("name")
                    if user_info.get("username"):
                        participant.participant_username = user_info.get("username")
                    if user_info.get("profile_pic"):
                        participant.participant_profile_pic = user_info.get("profile_pic")
                    participant.last_message_at = datetime.utcnow()

                # Parse attachments
                attachment_data = parse_message_attachments(message)
                message_type = MessageType.TEXT
                attachment_url = None
                attachment_type = None
                attachment_filename = None

                if attachment_data:
                    message_type = attachment_data["message_type"]
                    attachment_url = attachment_data.get("url")
                    attachment_type = attachment_data.get("content_type")
                    attachment_filename = attachment_data.get("filename")

                # Save message with correct direction
                db_message = Message(
                    user_id=account.user_id,
                    platform="facebook",
                    conversation_id=conv_id,
                    message_id=message_id,
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    direction=direction,
                    message_type=message_type,
                    content=message_text,
                    attachment_url=attachment_url,
                    attachment_type=attachment_type,
                    attachment_filename=attachment_filename,
                    status=MessageStatus.DELIVERED,
                )
                db.add(db_message)
                db.commit()
                db.refresh(db_message)

                logger.info(f"📤 Broadcasting message to WebSocket for user {account.user_id}...")

                # Broadcast to user via WebSocket for real-time updates
                try:
                    await manager.broadcast_to_user(
                        account.user_id,
                        "new_message",
                        {
                            "conversation_id": conv_id,
                            "message": {
                                "id": db_message.id,
                                "content": message_text,
                                "sender_id": sender_id,
                                "sender_name": user_info.get("name") if not is_echo else None,
                                "message_type": message_type.value,
                                "attachment_url": attachment_url,
                                "created_at": db_message.created_at.isoformat(),
                                "direction": "outgoing" if is_echo else "incoming"
                            }
                        }
                    )
                    logger.info(f"✅ WebSocket broadcast sent for message {message_id}")
                except Exception as ws_error:
                    logger.error(f"❌ WebSocket broadcast failed: {ws_error}", exc_info=True)

                logger.info(f"✅ Processed Facebook message {message_id} for conversation {conv_id}")

                # NEW: Process funnels and AI bots
                try:
                    workspace_id = account.workspace_id
                    if not workspace_id:
                        logger.warning("⚠️  Account has no workspace assigned, skipping funnel/bot processing")
                    else:
                        # Check if this is a new conversation
                        message_count = db.query(Message).filter(
                            Message.conversation_id == conv_id
                        ).count()
                        is_new_conversation = (message_count == 1)  # Only the message we just saved

                        # 1a. AI-driven funnel movement (analyze and move user to appropriate funnel)
                        ai_funnel_service = AIFunnelService()
                        moved_funnel_id = await ai_funnel_service.analyze_and_move_funnel(
                            conversation_id=conv_id,
                            workspace_id=workspace_id,
                            message_text=message_text,
                            db=db,
                        )
                        if moved_funnel_id:
                            logger.info(f"✅ AI moved user to funnel #{moved_funnel_id}")

                        # 1. Process funnels
                        funnel_service = FunnelService()
                        funnel_message = await funnel_service.process_message_for_funnels(
                            conversation_id=conv_id,
                            workspace_id=workspace_id,
                            message_text=message_text,
                            is_new_conversation=is_new_conversation,
                            db=db,
                        )

                        if funnel_message:
                            # Send funnel message
                            logger.info(f"📤 Sending funnel message: {funnel_message[:50]}...")
                            fb_service = FacebookService()
                            try:
                                await fb_service.send_message(
                                    recipient_id=sender_id,
                                    message_text=funnel_message,
                                    page_access_token=account.access_token,
                                )
                                logger.info("✅ Funnel message sent")
                            except Exception as send_error:
                                logger.error(f"❌ Failed to send funnel message: {send_error}")

                        # 2. Process AI bot (if not handled by funnel)
                        ai_bot_service = AIBotService()
                        ai_response = await ai_bot_service.process_incoming_message(
                            conversation_id=conv_id,
                            workspace_id=workspace_id,
                            message_text=message_text,
                            db=db,
                        )

                        if ai_response:
                            # Send AI response
                            logger.info(f"🤖 Sending AI response: {ai_response[:50]}...")
                            fb_service = FacebookService()
                            try:
                                await fb_service.send_message(
                                    recipient_id=sender_id,
                                    message_text=ai_response,
                                    page_access_token=account.access_token,
                                )
                                logger.info("✅ AI response sent")
                            except Exception as send_error:
                                logger.error(f"❌ Failed to send AI response: {send_error}")

                except Exception as e:
                    logger.error(f"❌ Error in funnel/bot processing: {e}", exc_info=True)
        else:
            logger.warning(f"⚠️  No connected account found for page_id: {recipient_id}")
    else:
        logger.info(f"⏭️  Event does not contain 'message' field, skipping")


@router.get("/instagram")
async def verify_instagram_webhook(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Verify Instagram webhook subscription"""
    # Get verify token from environment variable (same as Facebook)
    VERIFY_TOKEN = getattr(settings, 'WEBHOOK_VERIFY_TOKEN', 'my_secure_verify_token_12345')

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    else:
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/instagram")
async def instagram_webhook(request: Request):
    """Handle Instagram webhook events"""
    logger.info("=" * 80)
    logger.info("INSTAGRAM WEBHOOK RECEIVED")
    logger.info("=" * 80)

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    payload = await request.body()

    logger.info(f"Signature: {signature[:50]}...")
    logger.info(f"Payload size: {len(payload)} bytes")

    # Verify signature (supports both Instagram Business Login and Facebook Page-managed Instagram)
    if not verify_instagram_signature(payload, signature):
        logger.error("INSTAGRAM WEBHOOK SIGNATURE VERIFICATION FAILED!")
        raise HTTPException(status_code=403, detail="Invalid signature")

    logger.info("Signature verified successfully")

    # Process webhook
    data = await request.json()
    logger.info(f"Instagram webhook data: {data}")

    db = SessionLocal()
    try:
        # Handle webhook entries
        entries = data.get("entry", [])
        logger.info(f"Processing {len(entries)} Instagram webhook entries")

        for entry in entries:
            logger.info(f"Entry: {entry.get('id')}")
            # Handle messaging events
            messaging_events = entry.get("messaging", [])
            logger.info(f"Found {len(messaging_events)} messaging events")

            for messaging_event in messaging_events:
                logger.info(f"Processing Instagram messaging event: {messaging_event}")
                await handle_instagram_message(messaging_event, db)

        logger.info("✅ All Instagram webhook events processed successfully")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Error processing Instagram webhook: {e}", exc_info=True)
        raise
    finally:
        db.close()


async def handle_instagram_message(event: Dict[str, Any], db: Session):
    """Process an Instagram Direct message event"""
    logger.info(f"📸 Processing Instagram message event: {event.keys()}")

    sender_id = event.get("sender", {}).get("id")
    recipient_id = event.get("recipient", {}).get("id")

    logger.info(f"Sender ID: {sender_id}, Recipient ID: {recipient_id}")

    # Get message
    if "message" in event:
        message = event["message"]
        message_id = message.get("mid")
        message_text = message.get("text", "")
        is_echo = message.get("is_echo", False)

        logger.info(f"Message ID: {message_id}")
        logger.info(f"Message text: {message_text}")
        logger.info(f"Is echo: {is_echo}")

        # For echo messages, sender is the Instagram account, recipient is the user
        # For regular messages, sender is the user, recipient is the Instagram account
        if is_echo:
            ig_account_id = sender_id
            user_ig_id = recipient_id
            direction = MessageDirection.OUTGOING
            logger.info(f"Processing Instagram echo message (sent by account {ig_account_id} to user {user_ig_id})")
        else:
            ig_account_id = recipient_id
            user_ig_id = sender_id
            direction = MessageDirection.INCOMING
            logger.info(f"Processing Instagram incoming message (from user {user_ig_id} to account {ig_account_id})")

        # Find the connected account using ig_account_id
        # Support both Instagram connection types:
        # - Instagram Business Login: ig_account_id matches platform_user_id (Instagram Account ID)
        # - Facebook Page-managed Instagram: ig_account_id matches platform_user_id (Instagram Account ID)
        # IMPORTANT: Only process for ACTIVE accounts in ACTIVE workspaces
        logger.info(f"Looking for Instagram connected account with ig_account_id: {ig_account_id}")

        # Try platform_user_id first (should match Instagram Account ID)
        # Join with Workspace to check if workspace is active
        account = (
            db.query(ConnectedAccount)
            .join(Workspace, ConnectedAccount.workspace_id == Workspace.id)
            .filter(
                ConnectedAccount.platform == "instagram",
                ConnectedAccount.platform_user_id == ig_account_id,
                ConnectedAccount.is_active == True,
                Workspace.is_active == True,
            )
            .first()
        )

        # If not found, try page_id (fallback for old data or Facebook Page-managed)
        if not account:
            logger.info(f"Not found by platform_user_id, trying page_id...")
            account = (
                db.query(ConnectedAccount)
                .join(Workspace, ConnectedAccount.workspace_id == Workspace.id)
                .filter(
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.page_id == ig_account_id,
                    ConnectedAccount.is_active == True,
                    Workspace.is_active == True,
                )
                .first()
            )

        # IMPORTANT: Before IGAAL fallback, check if there's an INACTIVE account for this recipient_id
        # If found, we should REJECT the webhook - don't let other accounts process it
        if not account:
            inactive_account_check = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.platform == "instagram",
                    (ConnectedAccount.platform_user_id == ig_account_id) | (ConnectedAccount.page_id == ig_account_id),
                )
                .first()
            )

            if inactive_account_check:
                # We found an account for this recipient_id, but it's inactive or its workspace is inactive
                workspace = db.query(Workspace).filter(Workspace.id == inactive_account_check.workspace_id).first()
                if not inactive_account_check.is_active:
                    logger.warning(f"🚫 REJECTING webhook: Instagram account for {ig_account_id} is INACTIVE (is_active=False)")
                    logger.warning(f"🚫 Account ID: {inactive_account_check.id}, Username: @{inactive_account_check.platform_username}")
                    return  # Reject the webhook - don't process with another account
                if workspace and not workspace.is_active:
                    logger.warning(f"🚫 REJECTING webhook: Instagram account's workspace is INACTIVE (workspace.is_active=False)")
                    logger.warning(f"🚫 Account ID: {inactive_account_check.id}, Workspace ID: {workspace.id}")
                    return  # Reject the webhook - don't process with another account

        # Final fallback: Check Instagram Business Login accounts
        # For Instagram Business Login, /me returns Instagram-scoped User ID (stored in page_id)
        # But webhooks send Instagram Account ID (IGSID) which is DIFFERENT
        # We need to identify the account by checking conversations or using heuristics
        if not account:
            logger.info(f"Not found by page_id, checking Instagram Business Login accounts...")
            # Find all Instagram accounts with IGAAL tokens (Instagram Business Login)
            # Only check accounts in ACTIVE workspaces
            igaal_accounts = (
                db.query(ConnectedAccount)
                .join(Workspace, ConnectedAccount.workspace_id == Workspace.id)
                .filter(
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.access_token.like("IGAAL%"),
                    ConnectedAccount.is_active == True,
                    Workspace.is_active == True,
                )
                .all()
            )

            logger.info(f"Found {len(igaal_accounts)} active IGAAL accounts")

            # For each IGAAL account, try to identify if the webhook is for this account
            # by checking conversations for a participant matching the sender
            for igaal_account in igaal_accounts:
                try:
                    async with httpx.AsyncClient() as client:
                        # Query conversations to find if sender is a participant
                        # This confirms the webhook is for this account
                        response = await client.get(
                            f"https://graph.instagram.com/{igaal_account.page_id}/conversations",
                            params={
                                "platform": "instagram",
                                "fields": "participants",
                                "access_token": igaal_account.access_token,
                            },
                            timeout=10.0,
                        )

                        if response.status_code == 200:
                            conversations = response.json().get("data", [])
                            logger.info(f"Checking {len(conversations)} conversations for IGAAL account {igaal_account.id}")

                            # Check if any conversation has the sender as a participant
                            for conv in conversations:
                                participants = conv.get("participants", {}).get("data", [])
                                for participant in participants:
                                    participant_id = participant.get("id")
                                    # Check if this participant is the sender OR the recipient (our account)
                                    if participant_id == user_ig_id or participant_id == ig_account_id:
                                        logger.info(f"✅ Found matching conversation! Participant {participant_id} matches webhook data")
                                        logger.info(f"✅ This webhook is for IGAAL account {igaal_account.id} (@{igaal_account.platform_username})")

                                        # Update platform_user_id with the correct Instagram Account ID (IGSID)
                                        if igaal_account.platform_user_id != ig_account_id:
                                            old_id = igaal_account.platform_user_id
                                            igaal_account.platform_user_id = ig_account_id
                                            db.commit()
                                            logger.info(f"🔧 Auto-fixed platform_user_id: {old_id} → {ig_account_id}")

                                        account = igaal_account
                                        break
                                if account:
                                    break
                        else:
                            logger.warning(f"Failed to fetch conversations for IGAAL account {igaal_account.id}: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Failed to check IGAAL account {igaal_account.id}: {e}")
                    continue

                if account:
                    break

            # NOTE: We do NOT blindly assume webhooks are for the only IGAAL account
            # This would be dangerous as webhooks could be for a completely different
            # Instagram account. Only match when we can VERIFY via conversations.
            if not account and len(igaal_accounts) > 0:
                logger.warning(f"⚠️  Found {len(igaal_accounts)} IGAAL account(s) but none matched the webhook recipient_id: {ig_account_id}")
                logger.warning(f"⚠️  This webhook may be for a different Instagram account not connected in this system")

        # Log detailed info if account not found
        if not account:
            # Check if there's an inactive account or inactive workspace
            inactive_account = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.platform_user_id == ig_account_id,
                )
                .first()
            )
            if inactive_account:
                workspace = db.query(Workspace).filter(Workspace.id == inactive_account.workspace_id).first()
                if not inactive_account.is_active:
                    logger.warning(f"⚠️  Found Instagram account but it is INACTIVE (account.is_active=False)")
                if workspace and not workspace.is_active:
                    logger.warning(f"⚠️  Found Instagram account but its workspace is INACTIVE (workspace.is_active=False)")

        if account:
            logger.info(f"✅ Found Instagram connected account: {account.id} (user: {account.user_id})")
            # Check if message already exists
            existing = (
                db.query(Message).filter(Message.message_id == message_id).first()
            )

            if existing:
                logger.info(f"⏭️  Instagram message {message_id} already exists in database, skipping")
                return

            if not existing:
                logger.info(f"💾 Saving new Instagram message to database (direction: {direction})")
                # Create stable conversation ID using the user's Instagram ID (not the page)
                conv_id = create_stable_conversation_id("instagram", account.user_id, user_ig_id)

                # Fetch user information (the person chatting with the account)
                user_info = await fetch_sender_info(user_ig_id, account.access_token, "instagram")

                # Update or create conversation participant
                # IMPORTANT: Filter by workspace_id to allow same conversation in multiple workspaces
                participant = db.query(ConversationParticipant).filter(
                    ConversationParticipant.conversation_id == conv_id,
                    ConversationParticipant.workspace_id == account.workspace_id
                ).first()

                if not participant:
                    # Use reasonable defaults if fetch failed
                    # The username will be updated when messages are synced (which has access to conversation participants)
                    participant = ConversationParticipant(
                        conversation_id=conv_id,
                        platform="instagram",
                        platform_conversation_id=user_ig_id,
                        participant_id=user_ig_id,
                        participant_name=user_info.get("name") or "Instagram User",
                        participant_username=user_info.get("username"),  # May be None, will be updated on sync
                        participant_profile_pic=user_info.get("profile_pic"),
                        user_id=account.user_id,
                        workspace_id=account.workspace_id,
                        last_message_at=datetime.utcnow(),
                    )
                    db.add(participant)
                else:
                    # Update participant info and last message time (only if we got valid info)
                    if user_info.get("name"):
                        participant.participant_name = user_info.get("name")
                    if user_info.get("username"):
                        participant.participant_username = user_info.get("username")
                    if user_info.get("profile_pic"):
                        participant.participant_profile_pic = user_info.get("profile_pic")
                    participant.last_message_at = datetime.utcnow()

                # Parse attachments
                attachment_data = parse_message_attachments(message)
                message_type = MessageType.TEXT
                attachment_url = None
                attachment_type = None
                attachment_filename = None

                if attachment_data:
                    message_type = attachment_data["message_type"]
                    attachment_url = attachment_data.get("url")
                    attachment_type = attachment_data.get("content_type")
                    attachment_filename = attachment_data.get("filename")

                # Save message with correct direction
                db_message = Message(
                    user_id=account.user_id,
                    platform="instagram",
                    conversation_id=conv_id,
                    message_id=message_id,
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    direction=direction,
                    message_type=message_type,
                    content=message_text,
                    attachment_url=attachment_url,
                    attachment_type=attachment_type,
                    attachment_filename=attachment_filename,
                    status=MessageStatus.DELIVERED,
                )
                db.add(db_message)
                db.commit()
                db.refresh(db_message)

                logger.info(f"📤 Broadcasting message to WebSocket for user {account.user_id}...")

                # Broadcast to user via WebSocket for real-time updates
                try:
                    await manager.broadcast_to_user(
                        account.user_id,
                        "new_message",
                        {
                            "conversation_id": conv_id,
                            "message": {
                                "id": db_message.id,
                                "content": message_text,
                                "sender_id": sender_id,
                                "sender_name": user_info.get("name") if not is_echo else None,
                                "message_type": message_type.value,
                                "attachment_url": attachment_url,
                                "created_at": db_message.created_at.isoformat(),
                                "direction": "outgoing" if is_echo else "incoming"
                            }
                        }
                    )
                    logger.info(f"✅ WebSocket broadcast sent for message {message_id}")
                except Exception as ws_error:
                    logger.error(f"❌ WebSocket broadcast failed: {ws_error}", exc_info=True)

                logger.info(f"✅ Processed Instagram message {message_id} for conversation {conv_id}")

                # NEW: Process funnels and AI bots
                try:
                    workspace_id = account.workspace_id
                    if not workspace_id:
                        logger.warning("⚠️  Account has no workspace assigned, skipping funnel/bot processing")
                    else:
                        # Check if this is a new conversation
                        message_count = db.query(Message).filter(
                            Message.conversation_id == conv_id
                        ).count()
                        is_new_conversation = (message_count == 1)  # Only the message we just saved

                        # 1a. AI-driven funnel movement (analyze and move user to appropriate funnel)
                        ai_funnel_service = AIFunnelService()
                        moved_funnel_id = await ai_funnel_service.analyze_and_move_funnel(
                            conversation_id=conv_id,
                            workspace_id=workspace_id,
                            message_text=message_text,
                            db=db,
                        )
                        if moved_funnel_id:
                            logger.info(f"✅ AI moved user to funnel #{moved_funnel_id}")

                        # 1. Process funnels
                        funnel_service = FunnelService()
                        funnel_message = await funnel_service.process_message_for_funnels(
                            conversation_id=conv_id,
                            workspace_id=workspace_id,
                            message_text=message_text,
                            is_new_conversation=is_new_conversation,
                            db=db,
                        )

                        if funnel_message:
                            # Send funnel message
                            logger.info(f"📤 Sending funnel message: {funnel_message[:50]}...")
                            ig_service = InstagramService()
                            try:
                                await ig_service.send_message(
                                    recipient_id=sender_id,
                                    message_text=funnel_message,
                                    access_token=account.access_token,
                                    page_id=account.page_id or account.platform_user_id,
                                )
                                logger.info("✅ Funnel message sent")
                            except Exception as send_error:
                                logger.error(f"❌ Failed to send funnel message: {send_error}")

                        # 2. Process AI bot (if not handled by funnel)
                        ai_bot_service = AIBotService()
                        ai_response = await ai_bot_service.process_incoming_message(
                            conversation_id=conv_id,
                            workspace_id=workspace_id,
                            message_text=message_text,
                            db=db,
                        )

                        if ai_response:
                            # Send AI response
                            logger.info(f"🤖 Sending AI response: {ai_response[:50]}...")
                            ig_service = InstagramService()
                            try:
                                await ig_service.send_message(
                                    recipient_id=sender_id,
                                    message_text=ai_response,
                                    access_token=account.access_token,
                                    page_id=account.page_id or account.platform_user_id,
                                )
                                logger.info("✅ AI response sent")
                            except Exception as send_error:
                                logger.error(f"❌ Failed to send AI response: {send_error}")

                except Exception as e:
                    logger.error(f"❌ Error in funnel/bot processing: {e}", exc_info=True)
        else:
            logger.warning(f"⚠️  No connected Instagram account found for recipient_id: {recipient_id}")
            logger.warning(f"⚠️  Checked platform_user_id, page_id, and IGAAL token /me endpoints")
            logger.warning(f"⚠️  Make sure this Instagram account is connected in the dashboard")
    else:
        logger.info(f"⏭️  Instagram event does not contain 'message' field, skipping")
