import httpx
from typing import Dict, Any, Optional, List
from app.config import settings


class FacebookService:
    def __init__(self):
        self.graph_url = f"{settings.FACEBOOK_GRAPH_URL}/{settings.FACEBOOK_GRAPH_VERSION}"
        self.app_id = settings.FACEBOOK_APP_ID
        self.app_secret = settings.FACEBOOK_APP_SECRET

    def get_oauth_url(self, state: str = "") -> str:
        """Generate Facebook OAuth URL (includes Instagram and Business Manager permissions)"""
        from urllib.parse import quote

        scopes = [
            # Facebook Pages permissions
            "pages_messaging",
            "pages_manage_metadata",
            "pages_read_engagement",
            "pages_show_list",
            # Instagram permissions (for Instagram Business accounts linked to pages)
            "instagram_basic",
            "instagram_manage_messages",
            # Business Manager permissions (to access business and creator accounts)
            "business_management",
        ]
        scope_string = ",".join(scopes)

        # URL-encode the state parameter (it's a JSON string with special characters)
        encoded_state = quote(state, safe='')

        return (
            f"https://www.facebook.com/{settings.FACEBOOK_GRAPH_VERSION}/dialog/oauth?"
            f"client_id={self.app_id}&"
            f"redirect_uri={settings.FACEBOOK_REDIRECT_URI}&"
            f"state={encoded_state}&"
            f"scope={scope_string}"
        )

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.graph_url}/oauth/access_token",
                params={
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
                    "code": code,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_long_lived_token(self, short_lived_token: str) -> Dict[str, Any]:
        """Exchange short-lived token for long-lived token"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.graph_url}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "fb_exchange_token": short_lived_token,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Facebook"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.graph_url}/me",
                params={"access_token": access_token, "fields": "id,name,email"},
            )
            response.raise_for_status()
            return response.json()

    async def get_permissions(self, access_token: str) -> List[Dict[str, Any]]:
        """Get list of granted permissions for the access token"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.graph_url}/me/permissions",
                params={"access_token": access_token},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def get_user_pages(self, access_token: str) -> List[Dict[str, Any]]:
        """Get list of pages managed by user"""
        import logging
        logger = logging.getLogger(__name__)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.graph_url}/me/accounts",
                params={"access_token": access_token},
            )
            response.raise_for_status()
            data = response.json()

            # Log the full response for debugging
            logger.info(f"📄 Facebook API /me/accounts response: {data}")

            pages = data.get("data", [])
            if len(pages) == 0:
                logger.warning("⚠️  Facebook returned 0 pages. This means:")
                logger.warning("   1. User is not an ADMIN of any Facebook Pages")
                logger.warning("   2. User might be Editor/Moderator (not Admin)")
                logger.warning("   3. Or no pages exist for this account")

            return pages

    async def get_user_businesses(self, access_token: str) -> List[Dict[str, Any]]:
        """Get list of businesses managed by user (Business Manager)"""
        import logging
        logger = logging.getLogger(__name__)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.graph_url}/me/businesses",
                params={
                    "access_token": access_token,
                    "fields": "id,name"
                },
            )
            response.raise_for_status()
            data = response.json()

            logger.info(f"🏢 Facebook API /me/businesses response: {data}")
            businesses = data.get("data", [])
            logger.info(f"🏢 Found {len(businesses)} businesses")

            return businesses

    async def get_business_pages(self, business_id: str, access_token: str) -> List[Dict[str, Any]]:
        """Get pages owned by a specific business"""
        import logging
        logger = logging.getLogger(__name__)

        async with httpx.AsyncClient() as client:
            # Get client pages (pages owned by the business)
            response = await client.get(
                f"{self.graph_url}/{business_id}/client_pages",
                params={
                    "access_token": access_token,
                    "fields": "id,name,access_token"
                },
            )
            response.raise_for_status()
            data = response.json()

            logger.info(f"📄 Business {business_id} client_pages response: {data}")
            pages = data.get("data", [])
            logger.info(f"📄 Found {len(pages)} pages for business {business_id}")

            return pages

    async def get_all_user_pages(self, access_token: str) -> List[Dict[str, Any]]:
        """Get all pages accessible to user (both personal and Business Manager)"""
        import logging
        logger = logging.getLogger(__name__)

        all_pages = []

        # 1. Get personal pages (where user is direct admin)
        logger.info("📄 Fetching personal pages from /me/accounts...")
        personal_pages = await self.get_user_pages(access_token)
        all_pages.extend(personal_pages)
        logger.info(f"📄 Found {len(personal_pages)} personal pages")

        # 2. Get Business Manager pages
        logger.info("🏢 Fetching Business Manager pages...")
        try:
            businesses = await self.get_user_businesses(access_token)

            for business in businesses:
                business_id = business["id"]
                business_name = business.get("name", "Unknown Business")
                logger.info(f"🏢 Fetching pages for business: {business_name} (ID: {business_id})")

                try:
                    business_pages = await self.get_business_pages(business_id, access_token)

                    # Add business context to each page
                    for page in business_pages:
                        page["business_id"] = business_id
                        page["business_name"] = business_name

                    all_pages.extend(business_pages)
                    logger.info(f"📄 Added {len(business_pages)} pages from business {business_name}")
                except Exception as e:
                    logger.error(f"❌ Error fetching pages for business {business_id}: {e}")
                    continue
        except Exception as e:
            logger.warning(f"⚠️  Could not fetch Business Manager pages: {e}")

        logger.info(f"✅ Total pages found (personal + business): {len(all_pages)}")
        return all_pages

    async def get_page_conversations(
        self, page_id: str, page_access_token: str, max_pages: int = 5
    ) -> List[Dict[str, Any]]:
        """Get conversations for a page with pagination support"""
        all_conversations = []
        url = f"{self.graph_url}/{page_id}/conversations"
        params = {
            "access_token": page_access_token,
            "fields": "id,participants,updated_time",
            "limit": 50,  # Request more per page
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            pages_fetched = 0
            while url and pages_fetched < max_pages:
                response = await client.get(url, params=params if pages_fetched == 0 else None)
                response.raise_for_status()
                data = response.json()

                conversations = data.get("data", [])
                all_conversations.extend(conversations)
                pages_fetched += 1

                # Get next page URL if available
                paging = data.get("paging", {})
                url = paging.get("next")

                if url:
                    params = None  # Next URL includes all params

        return all_conversations

    async def get_conversation_messages(
        self, conversation_id: str, page_access_token: str
    ) -> List[Dict[str, Any]]:
        """Get messages from a conversation"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.graph_url}/{conversation_id}/messages",
                params={
                    "access_token": page_access_token,
                    "fields": "id,from,to,message,created_time,attachments",
                    "limit": 50,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def send_message(
        self,
        recipient_id: str,
        message_text: str,
        page_access_token: str,
        attachment_url: Optional[str] = None,
        attachment_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message via Facebook Messenger.

        Supports text messages and attachments (images, videos, audio, files).
        """
        import logging
        logger = logging.getLogger(__name__)

        async with httpx.AsyncClient() as client:
            # Build message payload
            message_data = {}

            if attachment_url and attachment_type:
                # Send attachment using "upload and send together" approach
                # NOTE: Do NOT set is_reusable when uploading and sending in one step
                # Per Facebook docs: "Do not set is_reusable=true in the payload for this case"
                logger.info(f"📤 Sending Facebook attachment: {attachment_type}")

                if "image" in attachment_type.lower():
                    message_data["attachment"] = {
                        "type": "image",
                        "payload": {"url": attachment_url}
                    }
                elif "video" in attachment_type.lower():
                    message_data["attachment"] = {
                        "type": "video",
                        "payload": {"url": attachment_url}
                    }
                elif "audio" in attachment_type.lower():
                    message_data["attachment"] = {
                        "type": "audio",
                        "payload": {"url": attachment_url}
                    }
                else:
                    message_data["attachment"] = {
                        "type": "file",
                        "payload": {"url": attachment_url}
                    }
            elif message_text:
                # Send text message
                message_data["text"] = message_text
            else:
                raise ValueError("Either message_text or attachment_url must be provided")

            payload = {
                "recipient": {"id": recipient_id},
                "message": message_data
            }

            logger.info(f"📤 Sending Facebook message to {recipient_id}")
            logger.info(f"📤 Payload: {payload}")

            response = await client.post(
                f"{self.graph_url}/me/messages",
                params={"access_token": page_access_token},
                json=payload,
            )

            logger.info(f"📤 Facebook API Response Status: {response.status_code}")

            # Log response for debugging
            try:
                response_data = response.json()
                logger.info(f"📤 Facebook API Response: {response_data}")
            except:
                logger.info(f"📤 Facebook API Response Text: {response.text}")

            # Handle specific Facebook errors
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "")
                    error_code = error_data.get("error", {}).get("error_subcode")

                    # 24-hour messaging window error
                    if "outside of allowed window" in error_message or error_code == 2534022:
                        raise ValueError(
                            "Cannot send message: This user hasn't messaged you in the last 24 hours. "
                            "Facebook's policy requires users to message you first or within 24 hours of their last message. "
                            "Wait for the user to send a message before replying."
                        )
                    elif error_message:
                        raise ValueError(f"Facebook API Error: {error_message}")
                except ValueError:
                    raise
                except:
                    pass

            response.raise_for_status()
            return response.json()

    async def subscribe_page_webhooks(
        self, page_id: str, page_access_token: str
    ) -> Dict[str, Any]:
        """Subscribe page to webhooks"""
        # Subscribe to all message-related webhook fields
        webhook_fields = [
            "messages",
            "messaging_postbacks",
            "messaging_optins",
            "message_deliveries",
            "message_reads",
            "messaging_referrals",
            "message_echoes"
        ]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.graph_url}/{page_id}/subscribed_apps",
                params={
                    "access_token": page_access_token,
                    "subscribed_fields": ",".join(webhook_fields),
                },
            )
            response.raise_for_status()
            return response.json()
