from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import httpx
import logging

from app.database import get_db
from app.models import Message, ConnectedAccount
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["Media"])


@router.get("/attachment/{message_id}")
async def get_attachment(
    message_id: str,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """
    Proxy endpoint to fetch media attachments with proper authentication.

    This solves the 403 Forbidden error when accessing Facebook CDN URLs directly.
    Facebook CDN URLs expire quickly, so we fetch fresh URLs from Graph API.
    """
    logger.info(f"📥 Fetching attachment for message {message_id}")

    # Get the message
    message = db.query(Message).filter(
        Message.message_id == message_id,
        Message.user_id == user_id
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not message.attachment_url:
        raise HTTPException(status_code=404, detail="Message has no attachment")

    # Get the connected account to get access token
    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user_id,
        ConnectedAccount.platform == message.platform,
        ConnectedAccount.is_active == True
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Connected account not found")

    try:
        logger.info(f"Original URL: {message.attachment_url[:100]}...")
        logger.info(f"Message type: {message.message_type}, Platform: {message.platform}")

        # Facebook CDN URLs expire quickly, fetch fresh URL from Graph API
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            # Fetch fresh attachment URL from Facebook Graph API
            graph_url = f"https://graph.facebook.com/{settings.FACEBOOK_GRAPH_VERSION}/{message.message_id}"
            params = {
                "access_token": account.access_token,
                "fields": "id,message,attachments"
            }

            logger.info(f"🔄 Fetching fresh URL from Graph API for message: {message.message_id}")

            graph_response = await client.get(graph_url, params=params)

            fresh_url = None

            if graph_response.status_code == 200:
                # Parse fresh attachment URL from Graph API response
                graph_data = graph_response.json()
                logger.info(f"✅ Graph API response received")

                attachments = graph_data.get("attachments", {}).get("data", [])
                if attachments and len(attachments) > 0:
                    attachment = attachments[0]
                    logger.info(f"Attachment type: {attachment.get('type')}")

                    # Try different URL fields based on attachment type
                    if "image_data" in attachment:
                        fresh_url = attachment["image_data"].get("url")
                        logger.info(f"Found image_data URL")
                    elif "video_data" in attachment:
                        fresh_url = attachment["video_data"].get("url")
                        logger.info(f"Found video_data URL")
                    elif "file_url" in attachment:
                        fresh_url = attachment.get("file_url")
                        logger.info(f"Found file_url")

                    # Check payload as fallback
                    if not fresh_url and "payload" in attachment:
                        fresh_url = attachment["payload"].get("url")
                        logger.info(f"Found payload URL")

                    if fresh_url:
                        logger.info(f"✅ Got fresh URL: {fresh_url[:100]}...")
                    else:
                        logger.warning(f"⚠️  No fresh URL found in Graph API response, using stored URL")
                        fresh_url = message.attachment_url
                else:
                    logger.warning(f"⚠️  No attachments in Graph API response, using stored URL")
                    fresh_url = message.attachment_url
            else:
                logger.error(f"❌ Graph API error: {graph_response.status_code} - {graph_response.text[:200]}")
                # Fallback to stored URL
                fresh_url = message.attachment_url
                logger.info(f"Falling back to stored URL")

            # Now fetch the actual media content
            logger.info(f"📡 Fetching media content...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
            }

            media_response = await client.get(fresh_url, headers=headers)

            if media_response.status_code != 200:
                logger.error(f"❌ Failed to fetch media: {media_response.status_code}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to fetch media: {media_response.status_code}"
                )

            # Get content type
            content_type = media_response.headers.get("content-type", "application/octet-stream")
            content_length = len(media_response.content)
            logger.info(f"✅ Successfully fetched media: {content_type}, {content_length} bytes")

            # Stream the response back to client
            return StreamingResponse(
                iter([media_response.content]),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'inline; filename="{message.attachment_filename or "attachment"}"',
                    "Cache-Control": "public, max-age=600"  # Cache for 10 minutes
                }
            )

    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP error fetching attachment: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch attachment: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error fetching attachment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/profile-pic")
async def proxy_profile_picture(url: str = Query(...)):
    """
    Proxy endpoint for Instagram/Facebook profile pictures.

    Instagram CDN URLs often have CORS issues when accessed directly from frontend.
    This endpoint proxies the request to avoid CORS and referrer policy issues.
    """
    logger.info(f"🖼️  Proxying profile picture: {url[:100]}...")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/*,*/*",
            }

            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning(f"⚠️  Failed to fetch profile pic: {response.status_code}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to fetch profile picture: {response.status_code}"
                )

            content_type = response.headers.get("content-type", "image/jpeg")
            logger.info(f"✅ Successfully fetched profile pic: {content_type}, {len(response.content)} bytes")

            return StreamingResponse(
                iter([response.content]),
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                    "Access-Control-Allow-Origin": "*",  # Allow CORS
                }
            )

    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP error fetching profile pic: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch profile picture: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error fetching profile pic: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
