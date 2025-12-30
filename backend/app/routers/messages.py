from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib
import httpx
import logging

from app.database import get_db
from app.models import Message, ConnectedAccount, MessageDirection, MessageStatus, MessageType, ConversationParticipant, ConversationAISettings, Funnel
from app.schemas import MessageCreate, MessageResponse, ConversationResponse
from app.services import FacebookService, InstagramService
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["Messages"])


def create_stable_conversation_id(platform: str, user_id: int, participant_id: str) -> str:
    """Create a stable conversation ID that doesn't change"""
    raw_id = f"{platform}_{user_id}_{participant_id}"
    # Create a hash for consistent ID
    return hashlib.md5(raw_id.encode()).hexdigest()[:16]


def parse_message_attachments(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse attachments from Facebook/Instagram message"""
    attachments = message.get("attachments", {}).get("data", [])
    if not attachments:
        return None

    attachment = attachments[0]  # Get first attachment
    attachment_type = attachment.get("mime_type", "").split("/")[0] if "mime_type" in attachment else attachment.get("image_data", {}).get("image_data") if "image_data" in attachment else None

    # Try different attachment structures
    url = attachment.get("image_data", {}).get("url") or attachment.get("video_data", {}).get("url") or attachment.get("file_url")

    if not url:
        return None

    result = {"url": url}

    # Map to our MessageType
    if "image" in str(attachment_type).lower() or "image_data" in attachment:
        result["message_type"] = MessageType.IMAGE
    elif "video" in str(attachment_type).lower() or "video_data" in attachment:
        result["message_type"] = MessageType.VIDEO
    elif "audio" in str(attachment_type).lower():
        result["message_type"] = MessageType.AUDIO
    else:
        result["message_type"] = MessageType.FILE

    # Get MIME type and filename
    if "mime_type" in attachment:
        result["content_type"] = attachment["mime_type"]
    if "name" in attachment:
        result["filename"] = attachment["name"]

    return result


async def fetch_sender_info(sender_id: str, access_token: str, platform: str) -> dict:
    """Fetch sender information from Facebook/Instagram API"""
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
            # Note: profile_picture_url is NOT available for other users (IGBusinessScopedID)
            # Only the account owner's profile has this field
            params = {
                "fields": "id,name,username",
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


@router.post("/send", response_model=MessageResponse)
async def send_message(
    message: MessageCreate,
    user_id: int = Query(...),
    account_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Send a message via Facebook or Instagram"""
    # Get the connected account
    account = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.id == account_id,
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.is_active == True,
        )
        .first()
    )

    if not account:
        raise HTTPException(status_code=404, detail="Connected account not found")

    try:
        # Determine message type
        message_type = MessageType.TEXT
        if message.attachment_url and message.attachment_type:
            if "image" in message.attachment_type.lower():
                message_type = MessageType.IMAGE
            elif "video" in message.attachment_type.lower():
                message_type = MessageType.VIDEO
            elif "audio" in message.attachment_type.lower():
                message_type = MessageType.AUDIO
            else:
                message_type = MessageType.FILE

        # Send message based on platform
        if message.platform == "facebook":
            fb_service = FacebookService()
            result = await fb_service.send_message(
                recipient_id=message.recipient_id,
                message_text=message.content or "",
                page_access_token=account.access_token,
                attachment_url=message.attachment_url,
                attachment_type=message.attachment_type
            )
            message_id = result.get("message_id")
        elif message.platform == "instagram":
            ig_service = InstagramService()
            # Instagram messages require page_id
            if not account.page_id:
                raise HTTPException(
                    status_code=400,
                    detail="Instagram account must have a linked Facebook Page"
                )
            result = await ig_service.send_message(
                recipient_id=message.recipient_id,
                message_text=message.content or "",
                access_token=account.access_token,
                page_id=account.page_id,
                attachment_url=message.attachment_url,
                attachment_type=message.attachment_type
            )
            message_id = result.get("message_id")
        else:
            raise HTTPException(status_code=400, detail="Invalid platform")

        # Create stable conversation ID
        conv_id = create_stable_conversation_id(message.platform, user_id, message.recipient_id)

        # Save message to database
        db_message = Message(
            user_id=user_id,
            platform=message.platform,
            conversation_id=conv_id,
            message_id=message_id,
            sender_id=account.platform_user_id,
            recipient_id=message.recipient_id,
            direction=MessageDirection.OUTGOING,
            message_type=message_type,
            content=message.content,
            attachment_url=message.attachment_url,
            attachment_type=message.attachment_type,
            status=MessageStatus.SENT,
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)

        return db_message

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.get("/conversations/by-user", response_model=List[ConversationResponse])
async def get_conversations_by_user(
    user_id: int = Query(...),
    platform: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all conversations for a user with participant info (deprecated - use /conversations with workspace_id)"""
    try:
        query = db.query(ConversationParticipant).filter(
            ConversationParticipant.user_id == user_id
        )

        if platform:
            query = query.filter(ConversationParticipant.platform == platform)

        participants = query.order_by(ConversationParticipant.last_message_at.desc()).all()

        # Deduplicate conversations by conversation_id (in case of duplicates in DB)
        seen_conversations = set()
        conversations = []
        for participant in participants:
            # Skip if we've already seen this conversation
            if participant.conversation_id in seen_conversations:
                continue
            seen_conversations.add(participant.conversation_id)

            # Get last message
            last_message = db.query(Message).filter(
                Message.conversation_id == participant.conversation_id
            ).order_by(Message.created_at.desc()).first()

            if last_message:  # Only include conversations with messages
                # Safely get ai_enabled with fallback for missing column
                ai_enabled = False
                try:
                    ai_enabled = participant.ai_enabled if participant.ai_enabled is not None else False
                except:
                    ai_enabled = False

                conversations.append(ConversationResponse(
                    conversation_id=participant.conversation_id,
                    platform=participant.platform,
                    participant_id=participant.participant_id,
                    participant_name=participant.participant_name,
                    participant_username=participant.participant_username,
                    participant_profile_pic=participant.participant_profile_pic,
                    last_message=last_message,
                    unread_count=0,  # TODO: Implement unread count
                    ai_enabled=ai_enabled,
                ))

        return conversations
    except Exception as e:
        # If column doesn't exist, return empty list or basic data
        logger.error(f"Error getting conversations: {e}")
        if "ai_enabled" in str(e):
            raise HTTPException(
                status_code=500,
                detail="Database migration required. Please run: heroku run python backend/migrate_add_message_fields.py"
            )
        raise HTTPException(status_code=500, detail=f"Failed to get conversations: {str(e)}")


@router.get("/conversation/{conversation_id}", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    user_id: int = Query(...),
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """Get messages from a specific conversation"""
    messages = (
        db.query(Message)
        .filter(
            Message.user_id == user_id, Message.conversation_id == conversation_id
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return messages


async def sync_account_messages(db: Session, account: ConnectedAccount, max_conversations: int = 10, max_messages_per_conv: int = 20) -> int:
    """
    Sync messages from Facebook/Instagram for a connected account.

    Args:
        db: Database session
        account: Connected account to sync
        max_conversations: Maximum number of conversations to sync (default: 10)
        max_messages_per_conv: Maximum messages per conversation (default: 20)

    Returns the number of messages synced.
    """
    synced_count = 0
    user_id = account.user_id

    try:
        if account.platform == "facebook":
            fb_service = FacebookService()
            # Get conversations
            conversations = await fb_service.get_page_conversations(
                account.page_id, account.access_token
            )

            # Limit conversations to prevent timeout
            conversations = conversations[:max_conversations]
            logger.info(f"🔄 Syncing {len(conversations)} conversations (limited from total)")

            for conv in conversations:
                # Get messages for each conversation
                messages = await fb_service.get_conversation_messages(
                    conv["id"], account.access_token
                )

                # Limit messages per conversation (newest first)
                messages = messages[:max_messages_per_conv]

                for msg in messages:
                    # Check if message already exists
                    existing = (
                        db.query(Message)
                        .filter(Message.message_id == msg["id"])
                        .first()
                    )

                    if not existing:
                        # Determine direction
                        direction = (
                            MessageDirection.OUTGOING
                            if msg["from"]["id"] == account.page_id
                            else MessageDirection.INCOMING
                        )

                        # Determine sender_id for stable conversation ID
                        sender_id = msg["from"]["id"]
                        other_participant = sender_id if direction == MessageDirection.INCOMING else (
                            msg["to"]["data"][0]["id"] if msg.get("to") else account.page_id
                        )

                        # Create stable conversation ID
                        conv_id = create_stable_conversation_id("facebook", user_id, other_participant)

                        # Create or update conversation participant for incoming messages
                        if direction == MessageDirection.INCOMING:
                            # Try to query participant, handle missing ai_enabled column
                            # IMPORTANT: Filter by workspace_id to allow same conversation in multiple workspaces
                            participant = None
                            try:
                                participant = db.query(ConversationParticipant).filter(
                                    ConversationParticipant.conversation_id == conv_id,
                                    ConversationParticipant.workspace_id == account.workspace_id
                                ).first()
                            except Exception as e:
                                # If ai_enabled column doesn't exist, query will fail
                                # Migration is required
                                if "ai_enabled" in str(e):
                                    raise HTTPException(
                                        status_code=500,
                                        detail="Database migration required. Run: heroku run python backend/migrate_add_message_fields.py"
                                    )
                                raise

                            # Fetch sender info
                            sender_info = await fetch_sender_info(sender_id, account.access_token, "facebook")

                            if not participant:
                                participant = ConversationParticipant(
                                    conversation_id=conv_id,
                                    platform="facebook",
                                    platform_conversation_id=sender_id,
                                    participant_id=sender_id,
                                    participant_name=sender_info.get("name"),
                                    participant_username=sender_info.get("username"),
                                    participant_profile_pic=sender_info.get("profile_pic"),
                                    user_id=user_id,
                                    workspace_id=account.workspace_id,
                                    last_message_at=datetime.utcnow(),
                                )
                                db.add(participant)
                            else:
                                # Update participant info
                                participant.participant_name = sender_info.get("name")
                                participant.participant_username = sender_info.get("username")
                                participant.participant_profile_pic = sender_info.get("profile_pic")
                                participant.last_message_at = datetime.utcnow()

                        # Parse attachments
                        attachment_data = parse_message_attachments(msg)
                        message_type = MessageType.TEXT
                        attachment_url = None
                        attachment_type = None
                        attachment_filename = None

                        if attachment_data:
                            message_type = attachment_data["message_type"]
                            attachment_url = attachment_data.get("url")
                            attachment_type = attachment_data.get("content_type")
                            attachment_filename = attachment_data.get("filename")

                        db_message = Message(
                            user_id=user_id,
                            platform="facebook",
                            conversation_id=conv_id,
                            message_id=msg["id"],
                            sender_id=sender_id,
                            recipient_id=msg["to"]["data"][0]["id"]
                            if msg.get("to")
                            else account.page_id,
                            direction=direction,
                            message_type=message_type,
                            content=msg.get("message"),
                            attachment_url=attachment_url,
                            attachment_type=attachment_type,
                            attachment_filename=attachment_filename,
                            status=MessageStatus.DELIVERED,
                        )
                        db.add(db_message)
                        synced_count += 1

        elif account.platform == "instagram":
            ig_service = InstagramService()
            # Get conversations (use page_id, not platform_user_id)
            # Instagram messages are managed through the linked Facebook Page
            conversations = await ig_service.get_conversations(
                account.page_id, account.access_token
            )

            # Limit conversations to prevent timeout
            conversations = conversations[:max_conversations]
            logger.info(f"🔄 Syncing {len(conversations)} Instagram conversations (limited from total)")

            for conv in conversations:
                # Extract participant usernames from conversation data for fallback
                # Instagram conversation includes: {'participants': {'data': [{'username': 'user1', 'id': '123'}, ...]}}
                conv_participants = {}
                if conv.get("participants") and conv["participants"].get("data"):
                    for p in conv["participants"]["data"]:
                        conv_participants[p["id"]] = p.get("username")

                # Get messages for each conversation
                messages = await ig_service.get_conversation_messages(
                    conv["id"], account.access_token
                )

                # Limit messages per conversation (newest first)
                messages = messages[:max_messages_per_conv]

                for msg in messages:
                    # Check if message already exists
                    existing = (
                        db.query(Message)
                        .filter(Message.message_id == msg["id"])
                        .first()
                    )

                    if not existing:
                        # Determine direction
                        direction = (
                            MessageDirection.OUTGOING
                            if msg["from"]["id"] == account.platform_user_id
                            else MessageDirection.INCOMING
                        )

                        # Determine sender_id for stable conversation ID
                        sender_id = msg["from"]["id"]
                        other_participant = sender_id if direction == MessageDirection.INCOMING else (
                            msg["to"]["data"][0]["id"] if msg.get("to") else account.platform_user_id
                        )

                        # Create stable conversation ID
                        conv_id = create_stable_conversation_id("instagram", user_id, other_participant)

                        # Create or update conversation participant for incoming messages
                        if direction == MessageDirection.INCOMING:
                            # Try to query participant, handle missing ai_enabled column
                            # IMPORTANT: Filter by workspace_id to allow same conversation in multiple workspaces
                            participant = None
                            try:
                                participant = db.query(ConversationParticipant).filter(
                                    ConversationParticipant.conversation_id == conv_id,
                                    ConversationParticipant.workspace_id == account.workspace_id
                                ).first()
                            except Exception as e:
                                # If ai_enabled column doesn't exist, query will fail
                                # Migration is required
                                if "ai_enabled" in str(e):
                                    raise HTTPException(
                                        status_code=500,
                                        detail="Database migration required. Run: heroku run python backend/migrate_add_message_fields.py"
                                    )
                                raise

                            # Fetch sender info
                            sender_info = await fetch_sender_info(sender_id, account.access_token, "instagram")

                            # Use conversation participant username as fallback if fetch_sender_info failed
                            # This is needed for Instagram Business Login where fetching other user info fails
                            if not sender_info.get("username") and sender_id in conv_participants:
                                fallback_username = conv_participants[sender_id]
                                if fallback_username:
                                    sender_info["username"] = fallback_username
                                    sender_info["name"] = fallback_username  # Use username as name too
                                    logger.info(f"👤 Using conversation participant username: @{fallback_username}")

                            if not participant:
                                participant = ConversationParticipant(
                                    conversation_id=conv_id,
                                    platform="instagram",
                                    platform_conversation_id=sender_id,
                                    participant_id=sender_id,
                                    participant_name=sender_info.get("name") or sender_info.get("username") or "Instagram User",
                                    participant_username=sender_info.get("username"),
                                    participant_profile_pic=sender_info.get("profile_pic"),
                                    user_id=user_id,
                                    workspace_id=account.workspace_id,
                                    last_message_at=datetime.utcnow(),
                                )
                                db.add(participant)
                            else:
                                # Update participant info (only if we got valid info)
                                if sender_info.get("name"):
                                    participant.participant_name = sender_info.get("name")
                                if sender_info.get("username"):
                                    participant.participant_username = sender_info.get("username")
                                if sender_info.get("profile_pic"):
                                    participant.participant_profile_pic = sender_info.get("profile_pic")
                                participant.last_message_at = datetime.utcnow()

                        # Parse attachments
                        attachment_data = parse_message_attachments(msg)
                        message_type = MessageType.TEXT
                        attachment_url = None
                        attachment_type = None
                        attachment_filename = None

                        if attachment_data:
                            message_type = attachment_data["message_type"]
                            attachment_url = attachment_data.get("url")
                            attachment_type = attachment_data.get("content_type")
                            attachment_filename = attachment_data.get("filename")

                        db_message = Message(
                            user_id=user_id,
                            platform="instagram",
                            conversation_id=conv_id,
                            message_id=msg["id"],
                            sender_id=sender_id,
                            recipient_id=msg["to"]["data"][0]["id"]
                            if msg.get("to")
                            else account.platform_user_id,
                            direction=direction,
                            message_type=message_type,
                            content=msg.get("message"),
                            attachment_url=attachment_url,
                            attachment_type=attachment_type,
                            attachment_filename=attachment_filename,
                            status=MessageStatus.DELIVERED,
                        )
                        db.add(db_message)
                        synced_count += 1

        db.commit()
        return synced_count

    except Exception as e:
        logger.error(f"Failed to sync messages for account {account.id}: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}"
        )


@router.get("/sync")
async def sync_messages(
    user_id: int = Query(...),
    account_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Sync messages from Facebook/Instagram"""
    account = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.id == account_id,
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.is_active == True,
        )
        .first()
    )

    if not account:
        raise HTTPException(status_code=404, detail="Connected account not found")

    try:
        synced_count = await sync_account_messages(db, account)

        # For Instagram Business Login accounts, try to extract and update Instagram Account ID
        if account.platform == "instagram" and account.connection_type == "instagram_business_login":
            logger.info("🔍 Attempting to extract Instagram Account ID from conversations...")
            try:
                ig_service = InstagramService()
                instagram_account_id = await ig_service.extract_instagram_account_id_from_conversations(
                    instagram_scoped_user_id=account.page_id,  # page_id stores Instagram-scoped User ID
                    access_token=account.access_token,
                    business_username=account.platform_username
                )

                if instagram_account_id and instagram_account_id != account.platform_user_id:
                    # Update platform_user_id with the correct Instagram Account ID
                    old_id = account.platform_user_id
                    account.platform_user_id = instagram_account_id
                    db.commit()
                    logger.info(f"✅ Updated platform_user_id: {old_id} → {instagram_account_id}")
                    logger.info(f"✅ Account now ready for webhook matching!")
                elif instagram_account_id:
                    logger.info("✅ Instagram Account ID already correct")
                else:
                    logger.warning("⚠️  Could not extract Instagram Account ID from conversations")

            except Exception as id_extract_error:
                logger.error(f"Failed to extract Instagram Account ID: {id_extract_error}")
                # Don't fail sync if ID extraction fails

        return {"synced_count": synced_count, "message": "Messages synced successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync messages: {str(e)}")


class AutoFunnelToggleRequest(BaseModel):
    enabled: bool


class SendMessageRequest(BaseModel):
    conversation_id: str
    workspace_id: int
    message_text: str
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None


class MoveFunnelRequest(BaseModel):
    funnel_id: Optional[int]
    disable_auto_funnel: bool = True


@router.get("/conversations", response_model=List[Dict[str, Any]])
async def get_conversations(
    workspace_id: int = Query(..., description="Workspace ID"),
    db: Session = Depends(get_db)
):
    """Get all conversations for a workspace"""
    try:
        # Get all participants for this workspace
        participants = db.query(ConversationParticipant).filter(
            ConversationParticipant.workspace_id == workspace_id
        ).all()

        conversations = []
        for participant in participants:
            # Get last message for this conversation
            last_message = db.query(Message).filter(
                Message.conversation_id == participant.conversation_id
            ).order_by(Message.created_at.desc()).first()

            # Get AI settings for funnel info
            ai_settings = db.query(ConversationAISettings).filter(
                ConversationAISettings.conversation_id == participant.conversation_id
            ).first()

            funnel_name = None
            if ai_settings and ai_settings.funnel_id:
                funnel = db.query(Funnel).filter(Funnel.id == ai_settings.funnel_id).first()
                if funnel:
                    funnel_name = funnel.name

            conversations.append({
                "id": participant.conversation_id,
                "participant_name": participant.participant_name,
                "participant_username": participant.participant_username,
                "participant_profile_pic": participant.participant_profile_pic,
                "platform": participant.platform,
                "last_message": last_message.content if last_message else None,
                "updated_at": last_message.created_at.isoformat() if last_message else participant.updated_at.isoformat(),
                "current_funnel": funnel_name
            })

        # Sort by most recent
        conversations.sort(key=lambda x: x["updated_at"], reverse=True)

        return conversations

    except Exception as e:
        logger.error(f"Failed to get conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversations: {str(e)}")


@router.get("/conversations/{conversation_id}/messages", response_model=List[Dict[str, Any]])
async def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """Get all messages for a conversation"""
    try:
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).all()

        return [
            {
                "id": msg.id,
                "message_text": msg.content or "",
                "content": msg.content or "",
                "direction": msg.direction.value,
                "created_at": msg.created_at.isoformat(),
                "sender_id": msg.sender_id,
                "message_type": msg.message_type.value if msg.message_type else "text",
                "attachment_url": msg.attachment_url,
                "attachment_type": msg.attachment_type,
                "attachment_filename": msg.attachment_filename,
            }
            for msg in messages
        ]

    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")


@router.get("/conversations/{conversation_id}/ai-settings")
async def get_conversation_ai_settings(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """Get AI settings for a conversation including auto-funnel status"""
    try:
        ai_settings = db.query(ConversationAISettings).filter(
            ConversationAISettings.conversation_id == conversation_id
        ).first()

        if not ai_settings:
            return {
                "auto_funnel_enabled": True,  # Default to enabled
                "funnel_id": None,
                "funnel_name": None,
                "ai_enabled": False
            }

        funnel_name = None
        if ai_settings.funnel_id:
            funnel = db.query(Funnel).filter(Funnel.id == ai_settings.funnel_id).first()
            if funnel:
                funnel_name = funnel.name

        return {
            "auto_funnel_enabled": ai_settings.auto_funnel_enabled,
            "funnel_id": ai_settings.funnel_id,
            "funnel_name": funnel_name,
            "ai_enabled": ai_settings.ai_enabled
        }

    except Exception as e:
        logger.error(f"Failed to get AI settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AI settings: {str(e)}")


@router.post("/conversations/{conversation_id}/auto-funnel")
async def toggle_auto_funnel(
    conversation_id: str,
    request: AutoFunnelToggleRequest,
    db: Session = Depends(get_db)
):
    """Toggle auto-funnel for a specific conversation"""
    try:
        # Get or create AI settings for this conversation
        ai_settings = db.query(ConversationAISettings).filter(
            ConversationAISettings.conversation_id == conversation_id
        ).first()

        if not ai_settings:
            # Get workspace_id from conversation participant
            participant = db.query(ConversationParticipant).filter(
                ConversationParticipant.conversation_id == conversation_id
            ).first()

            if not participant:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Create new AI settings
            ai_settings = ConversationAISettings(
                conversation_id=conversation_id,
                workspace_id=participant.workspace_id,
                auto_funnel_enabled=request.enabled,
                ai_enabled=False
            )
            db.add(ai_settings)
        else:
            # Update existing settings
            ai_settings.auto_funnel_enabled = request.enabled

        db.commit()

        logger.info(f"✅ Auto-funnel {'enabled' if request.enabled else 'disabled'} for conversation {conversation_id}")

        return {
            "success": True,
            "conversation_id": conversation_id,
            "auto_funnel_enabled": request.enabled
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to toggle auto-funnel: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle auto-funnel: {str(e)}")


@router.post("/messages/send")
async def send_message_endpoint(
    request: SendMessageRequest,
    db: Session = Depends(get_db)
):
    """Send a message to a conversation"""
    try:
        # Get conversation participant to find recipient
        participant = db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == request.conversation_id
        ).first()

        if not participant:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get connected account for this workspace
        account = db.query(ConnectedAccount).filter(
            ConnectedAccount.workspace_id == request.workspace_id,
            ConnectedAccount.platform == participant.platform
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail=f"No {participant.platform} account connected")

        # Send message via appropriate service
        if participant.platform == "facebook":
            service = FacebookService()
            result = await service.send_message(
                recipient_id=participant.participant_id,
                message_text=request.message_text,
                page_access_token=account.access_token,
                attachment_url=request.attachment_url,
                attachment_type=request.attachment_type
            )
        else:  # Instagram
            service = InstagramService()
            result = await service.send_message(
                recipient_id=participant.participant_id,
                message_text=request.message_text,
                access_token=account.access_token,
                page_id=account.page_id or account.platform_user_id,
                attachment_url=request.attachment_url,
                attachment_type=request.attachment_type
            )

        # Determine message type based on attachment
        msg_type = MessageType.TEXT
        if request.attachment_url and request.attachment_type:
            if request.attachment_type.startswith('image/'):
                msg_type = MessageType.IMAGE
            elif request.attachment_type.startswith('video/'):
                msg_type = MessageType.VIDEO
            elif request.attachment_type.startswith('audio/'):
                msg_type = MessageType.AUDIO
            else:
                msg_type = MessageType.FILE

        # Save message to database
        message = Message(
            user_id=account.user_id,
            platform=participant.platform,
            conversation_id=request.conversation_id,
            message_id=result.get("message_id", f"sent_{datetime.utcnow().timestamp()}"),
            sender_id=account.platform_user_id,
            recipient_id=participant.participant_id,
            content=request.message_text,
            message_type=msg_type,
            direction=MessageDirection.OUTGOING,
            status=MessageStatus.SENT,
            attachment_url=request.attachment_url,
            attachment_type=request.attachment_type
        )
        db.add(message)
        db.commit()

        logger.info(f"✅ Message sent and saved to conversation {request.conversation_id}")

        return {
            "success": True,
            "message_id": message.id,
            "platform_message_id": result.get("message_id")
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.post("/conversations/{conversation_id}/move-funnel")
async def move_conversation_to_funnel(
    conversation_id: str,
    request: MoveFunnelRequest,
    db: Session = Depends(get_db)
):
    """Move a conversation to a different funnel (manual assignment)"""
    try:
        # Get or create AI settings for this conversation
        ai_settings = db.query(ConversationAISettings).filter(
            ConversationAISettings.conversation_id == conversation_id
        ).first()

        if not ai_settings:
            # Get workspace_id from conversation participant
            participant = db.query(ConversationParticipant).filter(
                ConversationParticipant.conversation_id == conversation_id
            ).first()

            if not participant:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Create new AI settings
            ai_settings = ConversationAISettings(
                conversation_id=conversation_id,
                workspace_id=participant.workspace_id,
                funnel_id=request.funnel_id,
                auto_funnel_enabled=not request.disable_auto_funnel,
                ai_enabled=False
            )
            db.add(ai_settings)
        else:
            # Update existing settings
            ai_settings.funnel_id = request.funnel_id
            if request.disable_auto_funnel:
                ai_settings.auto_funnel_enabled = False

        db.commit()

        logger.info(f"✅ Moved conversation {conversation_id} to funnel {request.funnel_id}")
        if request.disable_auto_funnel:
            logger.info(f"   Auto-funnel disabled for this conversation")

        return {
            "success": True,
            "conversation_id": conversation_id,
            "funnel_id": request.funnel_id,
            "auto_funnel_enabled": ai_settings.auto_funnel_enabled
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to move conversation to funnel: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to move conversation: {str(e)}")
