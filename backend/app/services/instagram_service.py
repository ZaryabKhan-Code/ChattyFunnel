import httpx
from typing import Dict, Any, Optional, List
from app.config import settings


class InstagramService:
    def __init__(self):
        self.graph_url = f"{settings.FACEBOOK_GRAPH_URL}/{settings.FACEBOOK_GRAPH_VERSION}"
        self.app_id = settings.INSTAGRAM_APP_ID
        self.app_secret = settings.INSTAGRAM_APP_SECRET

    def get_oauth_url(self, state: str = "") -> str:
        """
        Generate Instagram Business Login OAuth URL.
        Uses the new Instagram Business Login flow with updated scopes.
        Note: Old scopes deprecated on January 27, 2025.
        """
        # New Instagram Business Login scopes (replacing old scopes)
        scopes = [
            "instagram_business_basic",              # Replaces instagram_basic
            "instagram_business_manage_messages",    # Replaces instagram_manage_messages
            "instagram_business_manage_comments",
            "instagram_business_content_publish",
        ]
        scope_string = ",".join(scopes)
        # Instagram Business Login uses instagram.com, not facebook.com
        return (
            f"https://www.instagram.com/oauth/authorize?"
            f"client_id={self.app_id}&"
            f"redirect_uri={settings.INSTAGRAM_REDIRECT_URI}&"
            f"response_type=code&"
            f"state={state}&"
            f"scope={scope_string}"
        )

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for short-lived Instagram User access token.
        Uses Instagram Business Login endpoint (not Facebook Graph API).
        Returns: {"data": [{"access_token": "...", "user_id": "...", "permissions": "..."}]}
        """
        async with httpx.AsyncClient() as client:
            # Instagram Business Login uses api.instagram.com for token exchange
            response = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.INSTAGRAM_REDIRECT_URI,
                    "code": code,
                },
            )
            response.raise_for_status()
            data = response.json()
            # Instagram Business Login returns data in a different format
            # {"data": [{"access_token": "...", "user_id": "...", "permissions": "..."}]}
            # We need to extract the first item from data array
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]
            return data

    async def get_long_lived_token(self, short_lived_token: str) -> Dict[str, Any]:
        """
        Exchange short-lived Instagram User access token for long-lived token (60 days).
        Uses Instagram Business Login endpoint with ig_exchange_token grant type.
        Returns: {"access_token": "...", "token_type": "bearer", "expires_in": 5183944}

        Note: Test tokens from Instagram's Token Generator in App Dashboard are already
        long-lived and cannot be exchanged. If you're testing, skip this step or use
        the test token directly.
        """
        import logging
        logger = logging.getLogger(__name__)

        async with httpx.AsyncClient() as client:
            # Instagram Business Login uses graph.instagram.com for long-lived tokens
            response = await client.get(
                "https://graph.instagram.com/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self.app_secret,
                    "access_token": short_lived_token,
                },
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                error_code = error_data.get("error", {}).get("code")
                logger.error(f"❌ Instagram token exchange failed: {error_msg} (code: {error_code})")
                logger.error(f"❌ Full error response: {error_data}")

                # If token is already long-lived (test tokens from dashboard)
                if "already" in error_msg.lower() or "invalid" in error_msg.lower():
                    logger.warning("⚠️  Token might already be long-lived (test token from dashboard)")
                    # Return the same token as if it was exchanged
                    return {
                        "access_token": short_lived_token,
                        "token_type": "bearer",
                        "expires_in": 5183944  # 60 days
                    }

                response.raise_for_status()

            return response.json()

 

    async def refresh_long_lived_token(self, long_lived_token: str) -> Dict[str, Any]:
        """
        Refresh a long-lived Instagram User access token for another 60 days.
        Requirements:
        - Token must be at least 24 hours old
        - Token must be valid (not expired)
        - User must have granted instagram_business_basic permission
        Returns: {"access_token": "...", "token_type": "bearer", "expires_in": 5183944}
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.instagram.com/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": long_lived_token,
                },
            )
            response.raise_for_status()
            return response.json()


    async def get_instagram_accounts(self, access_token: str, instagram_user_id: str) -> List[Dict[str, Any]]:
        """
        Get Instagram Business account info using Instagram Business Login.
        With Instagram Business Login, we get the Instagram-scoped user ID directly from token exchange.

        Args:
            access_token: Instagram User access token
            instagram_user_id: Instagram-scoped user ID from token exchange

        Returns:
            List of Instagram account dictionaries with profile info
        """
        import logging
        logger = logging.getLogger(__name__)
        instagram_accounts = []

        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"📱 Fetching Instagram account info for user ID: {instagram_user_id}...")

                # Use /me endpoint with Instagram Business Login (more reliable than user_id)
                # Instagram Business Login uses graph.instagram.com/me with the access token
                # Note: Only basic fields available - no profile_pic, followers_count, etc.
                ig_response = await client.get(
                    "https://graph.instagram.com/me",
                    params={
                        "fields": "id,username,name",
                        "access_token": access_token,
                    },
                )

                if ig_response.status_code != 200:
                    error_data = ig_response.json() if ig_response.text else {}
                    logger.error(f"❌ Instagram API Error: {error_data}")
                    ig_response.raise_for_status()

                ig_data = ig_response.json()
                logger.info(f"📊 Instagram account data: {ig_data}")

                # Get linked Facebook Page info (required for messaging)
                logger.info("🔍 Fetching linked Facebook Page for messaging...")
                try:
                    # Get Facebook Page connected to this Instagram account
                    # Use the ID from the profile response
                    account_id = ig_data.get("id", instagram_user_id)
                    page_response = await client.get(
                        f"{self.graph_url}/{account_id}",
                        params={
                            "fields": "connected_facebook_page{id,name,access_token}",
                            "access_token": access_token,
                        },
                    )

                    if page_response.status_code == 200:
                        page_data = page_response.json()

                        if "connected_facebook_page" in page_data:
                            fb_page = page_data["connected_facebook_page"]
                            ig_data["page_id"] = fb_page.get("id")
                            ig_data["page_name"] = fb_page.get("name")
                            ig_data["page_access_token"] = fb_page.get("access_token", access_token)
                            logger.info(f"✅ Linked Facebook Page: {fb_page.get('name')} (ID: {fb_page.get('id')})")
                        else:
                            logger.warning("⚠️  No Facebook Page linked - using Instagram access token")
                            ig_data["page_access_token"] = access_token
                    else:
                        logger.warning(f"⚠️  Could not fetch page info: {page_response.status_code}")
                        ig_data["page_access_token"] = access_token

                except Exception as page_error:
                    logger.warning(f"⚠️  Could not fetch linked page: {page_error}")
                    ig_data["page_access_token"] = access_token

                instagram_accounts.append(ig_data)
                logger.info(f"✅ Instagram account: @{ig_data.get('username')} (ID: {ig_data.get('id')})")
            except Exception as e:
                logger.error(f"❌ Error fetching Instagram account: {e}")
                raise

        logger.info(f"📱 Total Instagram accounts found: {len(instagram_accounts)}")
        return instagram_accounts

    async def get_instagram_profile(
        self, instagram_account_id: str, access_token: str
    ) -> Dict[str, Any]:
        """Get Instagram account profile information"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.graph_url}/{instagram_account_id}",
                params={
                    "fields": "id,username,name,profile_picture_url",
                    "access_token": access_token,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_instagram_profile_from_page(
        self, page_id: str, page_access_token: str
    ) -> Optional[Dict[str, Any]]:
        """Check if a Facebook Page has a linked Instagram Business account and return its profile"""
        try:
            async with httpx.AsyncClient() as client:
                # Check if page has linked Instagram Business account
                response = await client.get(
                    f"{self.graph_url}/{page_id}",
                    params={
                        "fields": "instagram_business_account{id,username,name,profile_picture_url}",
                        "access_token": page_access_token,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Return Instagram account data if it exists
                if "instagram_business_account" in data:
                    return data["instagram_business_account"]

                return None
        except Exception:
            return None

    async def get_conversations(
        self, page_id: str, access_token: str
    ) -> List[Dict[str, Any]]:
        """
        Get Instagram Direct message conversations.

        For Instagram Business Login: page_id is the Instagram Account ID
        For Facebook Page-managed: page_id is the Facebook Page ID

        Token type determines endpoint:
        - IGAAL* tokens -> graph.instagram.com
        - EAA* tokens -> graph.facebook.com
        """
        import logging
        logger = logging.getLogger(__name__)

        async with httpx.AsyncClient() as client:
            # Detect token type and use appropriate endpoint
            if access_token.startswith("IGAAL"):
                # Instagram Business Login token - use graph.instagram.com
                base_url = "https://graph.instagram.com"
                logger.info("🔑 Using Instagram Business Login endpoint")
            else:
                # Facebook token - use graph.facebook.com with version
                base_url = self.graph_url
                logger.info("🔑 Using Facebook Graph API endpoint")

            url = f"{base_url}/{page_id}/conversations"
            params = {
                "access_token": access_token,
                "fields": "id,participants,updated_time",
                "platform": "instagram",  # Filter to only Instagram conversations
            }

            logger.info(f"📞 Instagram API Request: GET {url}")
            logger.info(f"📞 Parameters: fields={params['fields']}, platform={params['platform']}")

            response = await client.get(url, params=params)

            logger.info(f"📞 Instagram API Response Status: {response.status_code}")

            # Log the response body even if there's an error
            try:
                response_data = response.json()
                logger.info(f"📞 Instagram API Response Body: {response_data}")
            except:
                logger.info(f"📞 Instagram API Response Text: {response.text}")

            response.raise_for_status()
            return response_data.get("data", [])

    async def get_conversation_messages(
        self, conversation_id: str, access_token: str
    ) -> List[Dict[str, Any]]:
        """
        Get messages from an Instagram conversation.

        Token type determines endpoint:
        - IGAAL* tokens -> graph.instagram.com
        - EAA* tokens -> graph.facebook.com
        """
        async with httpx.AsyncClient() as client:
            # Detect token type and use appropriate endpoint
            if access_token.startswith("IGAAL"):
                base_url = "https://graph.instagram.com"
            else:
                base_url = self.graph_url

            response = await client.get(
                f"{base_url}/{conversation_id}/messages",
                params={
                    "access_token": access_token,
                    "fields": "id,from,to,message,created_time,attachments",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def send_message(
        self,
        recipient_id: str,
        message_text: str,
        access_token: str,
        page_id: str,  # Can be Instagram Account ID or Facebook Page ID
        attachment_url: Optional[str] = None,
        attachment_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an Instagram Direct message.

        For Instagram Business Login: Use /{IG_ID}/messages or /me/messages
        For Facebook Page-managed Instagram: Use /{PAGE_ID}/messages

        Supports text messages and attachments (images, videos).
        Note: Instagram has a 1000 character limit for text messages.
        Note: Instagram does NOT support audio/webm format for voice notes.
              Supported formats: image/*, video/mp4
        """
        import logging
        logger = logging.getLogger(__name__)

        # Instagram has a 1000 character limit
        MAX_MESSAGE_LENGTH = 1000
        if message_text and len(message_text) > MAX_MESSAGE_LENGTH:
            logger.warning(f"⚠️  Message too long ({len(message_text)} chars). Truncating to {MAX_MESSAGE_LENGTH} chars.")
            message_text = message_text[:MAX_MESSAGE_LENGTH - 3] + "..."

        # Check for unsupported audio formats on Instagram
        if attachment_url and attachment_type:
            if attachment_type.startswith('audio/'):
                # Instagram doesn't support audio attachments in the same way as Facebook
                # WebM, MP3, WAV etc. are not supported
                raise ValueError(
                    "Instagram does not support voice notes or audio attachments. "
                    "Please send a text message, image, or video instead."
                )

        async with httpx.AsyncClient() as client:
            # Build message payload
            message_data = {}

            if attachment_url and attachment_type:
                # Send attachment using "upload and send together" approach
                # NOTE: Do NOT set is_reusable when uploading and sending in one step
                # Per Facebook/Instagram docs: "Do not set is_reusable=true in the payload for this case"
                # Instagram uses the same Graph API structure as Facebook for attachments
                logger.info(f"📤 Sending Instagram attachment: {attachment_type}")

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

            logger.info(f"📤 Sending Instagram message to {recipient_id} via account/page {page_id}")
            logger.info(f"📤 Payload: {payload}")

            # Detect token type and use appropriate endpoint
            if access_token.startswith("IGAAL"):
                # Instagram Business Login token - use graph.instagram.com
                url = f"https://graph.instagram.com/{page_id}/messages"
                logger.info("🔑 Using Instagram Business Login endpoint for message")
            else:
                # Facebook token - use graph.facebook.com with version
                url = f"{self.graph_url}/{page_id}/messages"
                logger.info("🔑 Using Facebook Graph API endpoint for message")

            response = await client.post(
                url,
                params={"access_token": access_token},
                json=payload,
            )

            logger.info(f"📤 Instagram API Response Status: {response.status_code}")

            # Log response for debugging
            try:
                response_data = response.json()
                logger.info(f"📤 Instagram API Response: {response_data}")
            except:
                logger.info(f"📤 Instagram API Response Text: {response.text}")

            # Handle specific Instagram errors
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "")
                    error_code = error_data.get("error", {}).get("error_subcode")

                    # 24-hour messaging window error
                    if "outside of allowed window" in error_message or error_code == 2534022:
                        raise ValueError(
                            "Cannot send message: This user hasn't messaged you in the last 24 hours. "
                            "Instagram's policy requires users to message you first or within 24 hours of their last message. "
                            "Wait for the user to send a message before replying."
                        )
                    elif error_message:
                        raise ValueError(f"Instagram API Error: {error_message}")
                except ValueError:
                    raise
                except:
                    pass

            response.raise_for_status()
            return response.json()

    async def extract_instagram_account_id_from_conversations(
        self,
        instagram_scoped_user_id: str,
        access_token: str,
        business_username: str
    ) -> Optional[str]:
        """
        Extract the Instagram Account ID from conversation participants.

        This is needed because Instagram Business Login provides two different IDs:
        1. Instagram-scoped User ID (from token exchange) - used for API calls
        2. Instagram Account ID (from conversation participants) - used in webhooks

        The Instagram Account ID only appears in conversation participants, NOT in /me endpoint.

        Args:
            instagram_scoped_user_id: The Instagram-scoped User ID for API calls
            access_token: The Instagram User access token
            business_username: The business account username to match in participants

        Returns:
            The Instagram Account ID if found, None otherwise
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info(f"🔍 Extracting Instagram Account ID from conversations for @{business_username}...")

            # Fetch conversations
            conversations = await self.get_conversations(instagram_scoped_user_id, access_token)

            if not conversations:
                logger.warning("⚠️  No conversations found - cannot extract Instagram Account ID")
                return None

            logger.info(f"📊 Found {len(conversations)} conversations to search")

            # Search through conversation participants
            for conv in conversations:
                participants = conv.get("participants", {}).get("data", [])

                for participant in participants:
                    participant_username = participant.get("username", "")
                    participant_id = participant.get("id", "")

                    # Match by username (business account appears in its own conversations)
                    if participant_username == business_username:
                        logger.info(f"✅ Found Instagram Account ID: {participant_id} (matched @{participant_username})")
                        return participant_id

            logger.warning(f"⚠️  Could not find @{business_username} in conversation participants")
            return None

        except Exception as e:
            logger.error(f"❌ Failed to extract Instagram Account ID: {e}")
            return None

    async def subscribe_webhooks(self, instagram_account_id: str, access_token: str) -> Dict[str, Any]:
        """
        Subscribe Instagram account to webhooks for real-time message notifications.

        For Instagram Business Login: Subscribe the Instagram account directly
        Endpoint: graph.instagram.com/{ig-account-id}/subscribed_apps
        """
        import logging
        logger = logging.getLogger(__name__)

        async with httpx.AsyncClient() as client:
            # Detect token type and use appropriate endpoint
            if access_token.startswith("IGAAL"):
                url = f"https://graph.instagram.com/{instagram_account_id}/subscribed_apps"
                logger.info("🔔 Using Instagram Business Login webhook endpoint")
            else:
                url = f"{self.graph_url}/{instagram_account_id}/subscribed_apps"
                logger.info("🔔 Using Facebook Graph API webhook endpoint")

            # Subscribe to all relevant webhook fields
            payload = {
                "subscribed_fields": "messages,messaging_postbacks,messaging_optins,messaging_referral,messaging_seen,message_reactions"
            }

            logger.info(f"🔔 Subscribing to webhooks: {url}")
            logger.info(f"🔔 Fields: {payload['subscribed_fields']}")

            response = await client.post(
                url,
                params={"access_token": access_token},
                data=payload,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ Webhook subscription failed: {error_data}")
                response.raise_for_status()

            result = response.json()
            logger.info(f"✅ Webhook subscription result: {result}")
            return result
