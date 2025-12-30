from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import logging
import traceback

from app.database import get_db
from app.models import User, ConnectedAccount, Workspace, WorkspaceMember
from app.services import FacebookService, InstagramService
from app.schemas import ConnectedAccountResponse
from app.routers.messages import sync_account_messages

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_or_create_default_workspace(user: User, db: Session) -> int:
    """Get or create default workspace for user. Returns workspace_id."""
    # Check if user already has a workspace
    workspace = (
        db.query(Workspace)
        .filter(Workspace.owner_id == user.id)
        .first()
    )

    if workspace:
        logger.info(f"Using existing workspace {workspace.id} for user {user.id}")
        return workspace.id

    # Create default workspace
    workspace = Workspace(
        owner_id=user.id,
        name=f"{user.username}'s Workspace",
        description="Default workspace",
        is_active=True,
    )
    db.add(workspace)
    db.flush()

    # Add owner as member
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
    )
    db.add(member)
    db.commit()

    logger.info(f"✅ Created default workspace {workspace.id} for user {user.id}")
    return workspace.id


@router.get("/facebook/login")
async def facebook_login(user_id: int = Query(...)):
    """Initiate Facebook OAuth flow"""
    fb_service = FacebookService()
    auth_url = fb_service.get_oauth_url(state=str(user_id))
    return {"auth_url": auth_url}


@router.get("/facebook/callback")
async def facebook_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle Facebook OAuth callback"""
    try:
        logger.info(f"Facebook callback received. State: {state}, Code: {code[:20]}...")
        fb_service = FacebookService()

        # Exchange code for token
        logger.info("Exchanging code for access token...")
        token_data = await fb_service.exchange_code_for_token(code)
        access_token = token_data.get("access_token")
        logger.info(f"Got access token: {access_token[:20] if access_token else 'None'}...")

        # Get long-lived token
        logger.info("Getting long-lived token...")
        long_lived_data = await fb_service.get_long_lived_token(access_token)
        long_lived_token = long_lived_data.get("access_token")
        expires_in = long_lived_data.get("expires_in", 5184000)  # Default 60 days
        logger.info(f"Got long-lived token, expires in: {expires_in} seconds")

        # Get user info
        logger.info("Getting user info...")
        user_info = await fb_service.get_user_info(long_lived_token)
        logger.info(f"User info: {user_info.get('name')}, ID: {user_info.get('id')}")

        # Check granted permissions
        logger.info("Checking granted permissions...")
        try:
            permissions = await fb_service.get_permissions(long_lived_token)
            granted = [p['permission'] for p in permissions if p['status'] == 'granted']
            logger.info(f"✅ Granted permissions: {granted}")
            if 'pages_show_list' not in granted:
                logger.warning("⚠️  WARNING: pages_show_list permission NOT granted!")
            if 'instagram_basic' not in granted:
                logger.warning("⚠️  WARNING: instagram_basic permission NOT granted!")
        except Exception as e:
            logger.warning(f"Could not fetch permissions: {e}")

        # Get user's pages (both personal and Business Manager)
        logger.info("Getting user pages (personal + Business Manager)...")
        pages = await fb_service.get_all_user_pages(long_lived_token)
        logger.info(f"Found {len(pages)} total pages")
        if len(pages) == 0:
            logger.warning("⚠️  No pages found! User may not have access to any pages")

        # Get or create user
        user_id = int(state) if state else None
        logger.info(f"Looking for user with ID: {user_id}")

        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            logger.info(f"User found: {user is not None}")
        else:
            user = (
                db.query(User).filter(User.username == user_info["name"]).first()
            )
            logger.info(f"User found by name: {user is not None}")

        if not user:
            logger.info("Creating new user...")
            user = User(
                username=user_info["name"],
                email=user_info.get("email"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created user with ID: {user.id}")

        # Get or create default workspace for user
        workspace_id = get_or_create_default_workspace(user, db)

        # Save connected accounts for each page
        logger.info(f"Processing {len(pages)} pages...")
        for page in pages:
            logger.info(f"Processing page: {page.get('name')}, ID: {page.get('id')}")

            # IMPORTANT: One Facebook per workspace rule
            # Check if there's already a Facebook page connected to this workspace
            existing_workspace_facebook = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.platform == "facebook",
                    ConnectedAccount.workspace_id == workspace_id,
                    ConnectedAccount.is_active == True,
                )
                .first()
            )

            if existing_workspace_facebook:
                if existing_workspace_facebook.page_id == page["id"]:
                    # Same Facebook page - update it
                    logger.info(f"Updating existing Facebook page {page['name']} in workspace {workspace_id}")
                else:
                    # Different Facebook page - skip (one Facebook per workspace)
                    logger.warning(f"Workspace {workspace_id} already has Facebook page {existing_workspace_facebook.page_name}")
                    logger.warning(f"Skipping Facebook page {page['name']} (one Facebook per workspace)")
                    continue

            # Check if this Facebook page is already connected to ANOTHER workspace
            existing_other_workspace = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.platform == "facebook",
                    ConnectedAccount.page_id == page["id"],
                    ConnectedAccount.is_active == True,
                    ConnectedAccount.workspace_id.isnot(None),
                    ConnectedAccount.workspace_id != workspace_id,
                )
                .first()
            )

            if existing_other_workspace:
                logger.warning(f"Facebook page {page['name']} is already connected to workspace {existing_other_workspace.workspace_id}")
                continue  # Skip this page, it's already connected to another workspace

            # Check if account already exists for this user
            existing_account = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.user_id == user.id,
                    ConnectedAccount.platform == "facebook",
                    ConnectedAccount.page_id == page["id"],
                )
                .first()
            )

            if existing_account:
                logger.info(f"Updating existing account ID: {existing_account.id}")
                # Update existing account
                existing_account.access_token = page["access_token"]
                existing_account.platform_username = page["name"]
                existing_account.connection_type = "facebook_page"
                existing_account.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in
                )
                existing_account.is_active = True
                existing_account.updated_at = datetime.utcnow()
            else:
                logger.info("Creating new connected account...")
                # Create new account
                connected_account = ConnectedAccount(
                    user_id=user.id,
                    workspace_id=workspace_id,
                    platform="facebook",
                    connection_type="facebook_page",
                    platform_user_id=user_info["id"],
                    platform_username=page["name"],
                    access_token=page["access_token"],
                    page_id=page["id"],
                    page_name=page["name"],
                    token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
                    is_active=True,
                )
                db.add(connected_account)

            # Subscribe page to webhooks
            try:
                logger.info(f"Subscribing webhooks for page {page['id']}...")
                await fb_service.subscribe_page_webhooks(page["id"], page["access_token"])
                logger.info("Webhook subscription successful")
            except Exception as e:
                logger.error(f"Failed to subscribe webhooks for page {page['id']}: {e}")

            # Check for linked Instagram Business account
            try:
                logger.info(f"Checking for Instagram account linked to page {page['id']}...")
                from app.services import InstagramService
                ig_service = InstagramService()

                ig_profile_response = await ig_service.get_instagram_profile_from_page(
                    page["id"], page["access_token"]
                )

                if ig_profile_response:
                    ig_account_id = ig_profile_response["id"]
                    ig_username = ig_profile_response.get("username", "Instagram Account")

                    logger.info(f"Found Instagram account: {ig_username} (ID: {ig_account_id})")

                    # IMPORTANT: One Instagram per workspace rule
                    # Check if there's ANY Instagram account already in this workspace
                    existing_workspace_instagram = (
                        db.query(ConnectedAccount)
                        .filter(
                            ConnectedAccount.platform == "instagram",
                            ConnectedAccount.workspace_id == workspace_id,
                            ConnectedAccount.is_active == True,
                        )
                        .first()
                    )

                    if existing_workspace_instagram:
                        # Already have Instagram in this workspace
                        if existing_workspace_instagram.platform_username == ig_username:
                            # Same Instagram account - update with Facebook Page info for better API access
                            logger.info(f"Updating existing Instagram account @{ig_username} with Facebook Page info")
                            # Store the Facebook Page ID for fallback API calls
                            # Keep existing connection_type as it determines the primary API
                            existing_workspace_instagram.updated_at = datetime.utcnow()
                            logger.info(f"Instagram account @{ig_username} already connected via {existing_workspace_instagram.connection_type}")
                        else:
                            # Different Instagram account - skip (one Instagram per workspace)
                            logger.warning(f"Workspace {workspace_id} already has Instagram @{existing_workspace_instagram.platform_username}")
                            logger.warning(f"Skipping Facebook page-linked Instagram @{ig_username} (one Instagram per workspace)")
                        continue  # Skip to next page

                    # Check if this Instagram account is already connected to ANOTHER workspace
                    existing_other_workspace_ig = (
                        db.query(ConnectedAccount)
                        .filter(
                            ConnectedAccount.platform == "instagram",
                            ConnectedAccount.platform_user_id == ig_account_id,
                            ConnectedAccount.is_active == True,
                            ConnectedAccount.workspace_id.isnot(None),
                            ConnectedAccount.workspace_id != workspace_id,
                        )
                        .first()
                    )

                    if existing_other_workspace_ig:
                        logger.warning(f"Instagram account {ig_username} is already connected to workspace {existing_other_workspace_ig.workspace_id}")
                        continue  # Skip this Instagram account

                    # Check if Instagram account already exists for this user (by exact platform_user_id)
                    existing_ig_account = (
                        db.query(ConnectedAccount)
                        .filter(
                            ConnectedAccount.user_id == user.id,
                            ConnectedAccount.platform == "instagram",
                            ConnectedAccount.platform_user_id == ig_account_id,
                        )
                        .first()
                    )

                    if existing_ig_account:
                        logger.info(f"Updating existing Instagram account ID: {existing_ig_account.id}")
                        existing_ig_account.access_token = page["access_token"]
                        existing_ig_account.platform_username = ig_username
                        existing_ig_account.page_id = page["id"]
                        existing_ig_account.connection_type = "facebook_page"
                        existing_ig_account.workspace_id = workspace_id
                        existing_ig_account.token_expires_at = datetime.utcnow() + timedelta(
                            seconds=expires_in
                        )
                        existing_ig_account.is_active = True
                        existing_ig_account.updated_at = datetime.utcnow()
                    else:
                        logger.info("Creating new Instagram connected account (Facebook Page-managed)...")
                        ig_connected_account = ConnectedAccount(
                            user_id=user.id,
                            workspace_id=workspace_id,
                            platform="instagram",
                            connection_type="facebook_page",
                            platform_user_id=ig_account_id,
                            platform_username=ig_username,
                            access_token=page["access_token"],
                            page_id=page["id"],
                            page_name=page["name"],
                            token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
                            is_active=True,
                        )
                        db.add(ig_connected_account)

                    logger.info(f"Instagram account {ig_username} linked successfully")
                else:
                    logger.info(f"No Instagram account linked to page {page['id']}")

            except Exception as ig_error:
                # Don't fail if Instagram linking fails
                logger.warning(f"Could not link Instagram account for page {page['id']}: {ig_error}")

        logger.info("Committing to database...")
        db.commit()
        logger.info("Database commit successful")

        # Auto-sync conversations for all connected pages
        logger.info("Starting auto-sync of conversations...")
        total_synced = 0
        for page in pages:
            try:
                # Get the connected account we just created/updated
                account = (
                    db.query(ConnectedAccount)
                    .filter(
                        ConnectedAccount.user_id == user.id,
                        ConnectedAccount.platform == "facebook",
                        ConnectedAccount.page_id == page["id"],
                    )
                    .first()
                )

                if account:
                    logger.info(f"Syncing conversations for page {page['name']}...")
                    synced_count = await sync_account_messages(db, account)
                    total_synced += synced_count
                    logger.info(f"Synced {synced_count} messages from page {page['name']}")
            except Exception as sync_error:
                # Don't fail the OAuth flow if sync fails
                logger.error(f"Failed to auto-sync page {page['name']}: {sync_error}")

        logger.info(f"Auto-sync completed. Total messages synced: {total_synced}")

        # Redirect to frontend success page
        from app.config import settings
        redirect_url = f"{settings.FRONTEND_URL}/dashboard?success=facebook"
        logger.info(f"Redirecting to: {redirect_url}")
        return RedirectResponse(
            url=redirect_url
        )

    except Exception as e:
        logger.error(f"Facebook OAuth error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@router.get("/instagram/login")
async def instagram_login(user_id: int = Query(...)):
    """Initiate Instagram OAuth flow"""
    ig_service = InstagramService()
    auth_url = ig_service.get_oauth_url(state=str(user_id))
    return {"auth_url": auth_url}


@router.get("/instagram/callback")
async def instagram_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle Instagram Business Login OAuth callback"""
    try:
        logger.info(f"Instagram callback received. State: {state}, Code: {code[:20]}...")
        ig_service = InstagramService()

        # Exchange code for short-lived token (Instagram Business Login returns different format)
        logger.info("Exchanging code for short-lived Instagram User access token...")
        token_data = await ig_service.exchange_code_for_token(code)

        # Instagram Business Login returns: {"access_token": "...", "user_id": "...", "permissions": "..."}
        access_token = token_data.get("access_token")
        instagram_user_id = token_data.get("user_id")
        permissions = token_data.get("permissions", "")


        logger.info(f"Got short-lived token: {access_token[:20] if access_token else 'None'}...")
        logger.info(f"Instagram User ID: {instagram_user_id}")
        logger.info(f"Granted permissions: {permissions}")

        # Get long-lived token (60 days)
        logger.info("Exchanging for long-lived Instagram User access token...")
        long_lived_data = await ig_service.get_long_lived_token(access_token)
        long_lived_token = long_lived_data.get("access_token")
        expires_in = long_lived_data.get("expires_in", 5184000)  # Default 60 days
        logger.info(f"Got long-lived token, expires in: {expires_in} seconds ({expires_in / 86400:.0f} days)")

        # Get Instagram account info using Instagram-scoped user ID
        logger.info("Getting Instagram account profile...")
        ig_accounts = await ig_service.get_instagram_accounts(long_lived_token, instagram_user_id)

        logger.info(f"Found {len(ig_accounts)} Instagram accounts")

        # Get or create user
        user_id = int(state) if state else None
        logger.info(f"Looking for user with ID: {user_id}")

        if not user_id:
            raise HTTPException(status_code=400, detail="User ID is required")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found with ID: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"User found: {user.username}")

        # Get or create default workspace for user
        workspace_id = get_or_create_default_workspace(user, db)

        # Save connected Instagram accounts
        logger.info(f"Processing {len(ig_accounts)} Instagram accounts...")
        for ig_account in ig_accounts:
            # Instagram Business Login has TWO important IDs:
            # 1. instagram_user_id (from token exchange) = Instagram-scoped User ID for API calls
            # 2. ig_account["id"] (from /me endpoint) = Instagram Account ID for webhooks
            instagram_account_id = ig_account["id"]  # For webhooks (recipient_id)
            instagram_scoped_user_id = instagram_user_id  # For API calls (/{id}/conversations)

            logger.info(f"Instagram Account ID (webhooks): {instagram_account_id}")
            logger.info(f"Instagram Scoped User ID (API): {instagram_scoped_user_id}")
            logger.info(f"Instagram profile: @{ig_account.get('username')}")

            access_token = ig_account.get("page_access_token", long_lived_token)

            # IMPORTANT: One Instagram per workspace rule
            # Check if there's already an Instagram account in this workspace
            existing_workspace_instagram = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.workspace_id == workspace_id,
                    ConnectedAccount.is_active == True,
                )
                .first()
            )

            if existing_workspace_instagram:
                if existing_workspace_instagram.platform_username == ig_account.get("username"):
                    # Same Instagram account - update it with new Instagram Business Login credentials
                    logger.info(f"Updating existing Instagram account @{ig_account.get('username')} with Instagram Business Login")
                    existing_workspace_instagram.access_token = access_token
                    existing_workspace_instagram.platform_user_id = instagram_account_id
                    existing_workspace_instagram.page_id = instagram_scoped_user_id
                    existing_workspace_instagram.connection_type = "instagram_business_login"
                    existing_workspace_instagram.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                    existing_workspace_instagram.is_active = True
                    existing_workspace_instagram.updated_at = datetime.utcnow()
                    logger.info(f"Instagram account @{ig_account.get('username')} updated successfully")
                    continue  # Already updated, skip to next account
                else:
                    # Different Instagram account - skip (one Instagram per workspace)
                    logger.warning(f"Workspace {workspace_id} already has Instagram @{existing_workspace_instagram.platform_username}")
                    logger.warning(f"Skipping Instagram @{ig_account.get('username')} (one Instagram per workspace)")
                    continue

            # Check if this Instagram account is already connected to ANOTHER workspace
            existing_other_workspace = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.platform_user_id == instagram_account_id,
                    ConnectedAccount.is_active == True,
                    ConnectedAccount.workspace_id.isnot(None),
                    ConnectedAccount.workspace_id != workspace_id,
                )
                .first()
            )

            if existing_other_workspace:
                logger.warning(f"Instagram account @{ig_account.get('username')} is already connected to workspace {existing_other_workspace.workspace_id}")
                continue  # Skip this Instagram account

            # Check if account already exists for this user (check by Instagram Account ID)
            existing_account = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.user_id == user.id,
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.platform_user_id == instagram_account_id,
                )
                .first()
            )

            if existing_account:
                logger.info(f"Updating existing Instagram account ID: {existing_account.id}")
                # Update existing account
                existing_account.access_token = access_token
                existing_account.platform_username = ig_account.get("username")
                # Store Instagram-scoped User ID for API calls
                existing_account.page_id = instagram_scoped_user_id
                existing_account.connection_type = "instagram_business_login"
                existing_account.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in
                )
                existing_account.is_active = True
                existing_account.updated_at = datetime.utcnow()
            else:
                logger.info("Creating new Instagram connected account...")
                # Create new account
                # For Instagram Business Login:
                # - platform_user_id = Instagram Account ID (for webhooks)
                # - page_id = Instagram-scoped User ID (for API calls)
                # - connection_type = 'instagram_business_login' (for API endpoint selection)
                connected_account = ConnectedAccount(
                    user_id=user.id,
                    workspace_id=workspace_id,
                    platform="instagram",
                    connection_type="instagram_business_login",
                    platform_user_id=instagram_account_id,  # Instagram Account ID (webhooks)
                    platform_username=ig_account.get("username"),
                    access_token=access_token,
                    page_id=instagram_scoped_user_id,  # Instagram-scoped User ID (API calls)
                    token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
                    is_active=True,
                )
                db.add(connected_account)

        logger.info("Committing to database...")
        db.commit()
        logger.info("Database commit successful")

        # Subscribe Instagram account to webhooks
        logger.info("Subscribing Instagram account to webhooks...")
        # Use Instagram-scoped User ID for webhook subscription (API endpoint)
        try:
            logger.info(f"Subscribing webhooks for Instagram scoped user ID {instagram_user_id}...")
            await ig_service.subscribe_webhooks(instagram_user_id, long_lived_token)
            logger.info("✅ Webhook subscription successful")
        except Exception as webhook_error:
            logger.error(f"⚠️  Failed to subscribe webhooks: {webhook_error}")
            # Don't fail the OAuth flow if webhook subscription fails

        # Auto-sync conversations for all connected Instagram accounts
        logger.info("Starting auto-sync of Instagram conversations...")
        total_synced = 0
        for ig_account in ig_accounts:
            try:
                # Get the connected account we just created/updated
                account = (
                    db.query(ConnectedAccount)
                    .filter(
                        ConnectedAccount.user_id == user.id,
                        ConnectedAccount.platform == "instagram",
                        ConnectedAccount.platform_user_id == ig_account["id"],
                    )
                    .first()
                )

                if account:
                    logger.info(f"Syncing conversations for Instagram account {ig_account['id']}...")
                    synced_count = await sync_account_messages(db, account)
                    total_synced += synced_count
                    logger.info(f"Synced {synced_count} messages from Instagram account")
            except Exception as sync_error:
                # Don't fail the OAuth flow if sync fails
                logger.error(f"Failed to auto-sync Instagram account {ig_account['id']}: {sync_error}")

        logger.info(f"Auto-sync completed. Total messages synced: {total_synced}")

        # Extract Instagram Account ID from conversations for webhook matching
        # This is CRITICAL: Instagram Business Login provides two IDs:
        # 1. Instagram-scoped User ID (from token exchange) - for API calls, stored in page_id
        # 2. Instagram Account ID (from conversation participants) - for webhooks, should be in platform_user_id
        logger.info("🔍 Attempting to extract Instagram Account ID from conversations...")
        for ig_account in ig_accounts:
            try:
                account = (
                    db.query(ConnectedAccount)
                    .filter(
                        ConnectedAccount.user_id == user.id,
                        ConnectedAccount.platform == "instagram",
                        ConnectedAccount.page_id == instagram_user_id,
                    )
                    .first()
                )

                if account:
                    # Extract Instagram Account ID from conversation participants
                    instagram_account_id = await ig_service.extract_instagram_account_id_from_conversations(
                        instagram_scoped_user_id=instagram_user_id,
                        access_token=long_lived_token,
                        business_username=ig_account.get("username")
                    )

                    if instagram_account_id:
                        # Update platform_user_id with the correct Instagram Account ID
                        old_id = account.platform_user_id
                        account.platform_user_id = instagram_account_id
                        db.commit()
                        logger.info(f"✅ Updated platform_user_id: {old_id} → {instagram_account_id}")
                        logger.info(f"✅ Account now ready for webhook matching!")
                    else:
                        logger.warning("⚠️  No conversations found - platform_user_id will be updated when first conversation is synced")
                        logger.info(f"ℹ️  Current platform_user_id: {account.platform_user_id} (Instagram-scoped User ID)")
                        logger.info(f"ℹ️  Webhooks will auto-fix this on first message received")

            except Exception as id_extract_error:
                logger.error(f"Failed to extract Instagram Account ID: {id_extract_error}")
                # Don't fail OAuth flow if ID extraction fails

        # Redirect to frontend success page
        from app.config import settings
        redirect_url = f"{settings.FRONTEND_URL}/dashboard?success=instagram"
        logger.info(f"Redirecting to: {redirect_url}")
        return RedirectResponse(
            url=redirect_url
        )

    except Exception as e:
        logger.error(f"Instagram OAuth error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
