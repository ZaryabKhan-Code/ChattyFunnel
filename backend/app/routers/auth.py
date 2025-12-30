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
async def facebook_login(user_id: int = Query(...), workspace_id: Optional[int] = Query(None)):
    """Initiate Facebook OAuth flow"""
    fb_service = FacebookService()
    # Encode both user_id and workspace_id in state
    import json
    state_data = {"user_id": user_id, "workspace_id": workspace_id}
    auth_url = fb_service.get_oauth_url(state=json.dumps(state_data))
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

        # Parse state to get user_id and workspace_id
        import json
        user_id = None
        requested_workspace_id = None

        if state:
            try:
                # Try to parse as JSON (new format)
                state_data = json.loads(state)
                user_id = state_data.get("user_id")
                requested_workspace_id = state_data.get("workspace_id")
                logger.info(f"Parsed state: user_id={user_id}, workspace_id={requested_workspace_id}")
            except json.JSONDecodeError:
                # Fallback to old format (just user_id as string)
                user_id = int(state)
                logger.info(f"Legacy state format, user_id={user_id}")

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

        # Use requested workspace_id if provided, otherwise get/create default
        if requested_workspace_id:
            # Verify the user has access to this workspace
            workspace = db.query(Workspace).filter(Workspace.id == requested_workspace_id).first()
            if workspace:
                workspace_id = requested_workspace_id
                logger.info(f"Using requested workspace {workspace_id}")
            else:
                workspace_id = get_or_create_default_workspace(user, db)
                logger.warning(f"Requested workspace {requested_workspace_id} not found, using default {workspace_id}")
        else:
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
                    # Different Facebook page - redirect with error (one Facebook per workspace)
                    logger.warning(f"Workspace {workspace_id} already has Facebook page {existing_workspace_facebook.page_name}")
                    logger.warning(f"Cannot add Facebook page {page['name']} (one Facebook per workspace)")
                    from app.config import settings
                    error_msg = f"This workspace already has Facebook page '{existing_workspace_facebook.page_name}' connected. Disconnect it first to connect a different page."
                    redirect_url = f"{settings.FRONTEND_URL}/dashboard?error=facebook_conflict&message={error_msg}"
                    return RedirectResponse(url=redirect_url)

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
                from app.config import settings
                error_msg = f"Facebook page '{page['name']}' is already connected to another workspace. Each Facebook page can only be in one workspace."
                redirect_url = f"{settings.FRONTEND_URL}/dashboard?error=facebook_in_use&message={error_msg}"
                return RedirectResponse(url=redirect_url)

            # Check if account already exists for this user in the REQUESTED workspace
            existing_account_in_workspace = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.user_id == user.id,
                    ConnectedAccount.platform == "facebook",
                    ConnectedAccount.page_id == page["id"],
                    ConnectedAccount.workspace_id == workspace_id,
                )
                .first()
            )

            # Also check if there's an account in ANY workspace (for migration)
            existing_account_any_workspace = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.user_id == user.id,
                    ConnectedAccount.platform == "facebook",
                    ConnectedAccount.page_id == page["id"],
                )
                .first()
            )

            if existing_account_in_workspace:
                # Account exists in the requested workspace - just update it
                logger.info(f"Updating existing account ID: {existing_account_in_workspace.id} in workspace {workspace_id}")
                existing_account_in_workspace.access_token = page["access_token"]
                existing_account_in_workspace.platform_username = page["name"]
                existing_account_in_workspace.page_name = page["name"]
                existing_account_in_workspace.connection_type = "facebook_page"
                existing_account_in_workspace.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in
                )
                existing_account_in_workspace.is_active = True
                existing_account_in_workspace.updated_at = datetime.utcnow()
            elif existing_account_any_workspace and not existing_account_any_workspace.is_active:
                # Account exists in another workspace but is INACTIVE - move it to new workspace
                old_workspace = existing_account_any_workspace.workspace_id
                logger.info(f"Moving inactive Facebook account from workspace {old_workspace} to workspace {workspace_id}")
                existing_account_any_workspace.workspace_id = workspace_id
                existing_account_any_workspace.access_token = page["access_token"]
                existing_account_any_workspace.platform_username = page["name"]
                existing_account_any_workspace.page_name = page["name"]
                existing_account_any_workspace.connection_type = "facebook_page"
                existing_account_any_workspace.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in
                )
                existing_account_any_workspace.is_active = True
                existing_account_any_workspace.updated_at = datetime.utcnow()
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
                            # Different Instagram account - skip adding it (one Instagram per workspace)
                            # For Facebook page connections, we just skip the linked Instagram, not fail the whole connection
                            logger.warning(f"Workspace {workspace_id} already has Instagram @{existing_workspace_instagram.platform_username}")
                            logger.warning(f"Skipping Facebook page-linked Instagram @{ig_username} (one Instagram per workspace)")
                            logger.info(f"Facebook page {page['name']} will still be connected, just without the linked Instagram")
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
                        # Instagram already in another workspace - skip it for Facebook page connections
                        logger.warning(f"Instagram account @{ig_username} is already connected to workspace {existing_other_workspace_ig.workspace_id}")
                        logger.warning(f"Skipping Facebook page-linked Instagram @{ig_username} (already in another workspace)")
                        logger.info(f"Facebook page {page['name']} will still be connected, just without the linked Instagram")
                        continue  # Skip to next page, but don't fail the Facebook connection

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

        # Auto-sync Instagram conversations for Facebook page-linked Instagram accounts
        logger.info("Starting auto-sync of Instagram conversations...")
        ig_synced = 0
        for page in pages:
            try:
                # Get the Instagram account linked to this page
                ig_account = (
                    db.query(ConnectedAccount)
                    .filter(
                        ConnectedAccount.user_id == user.id,
                        ConnectedAccount.platform == "instagram",
                        ConnectedAccount.page_id == page["id"],
                        ConnectedAccount.is_active == True,
                    )
                    .first()
                )

                if ig_account:
                    logger.info(f"Syncing conversations for Instagram @{ig_account.platform_username}...")
                    synced_count = await sync_account_messages(db, ig_account)
                    ig_synced += synced_count
                    logger.info(f"Synced {synced_count} messages from Instagram @{ig_account.platform_username}")
            except Exception as sync_error:
                # Don't fail the OAuth flow if sync fails
                logger.error(f"Failed to auto-sync Instagram for page {page['id']}: {sync_error}")

        logger.info(f"Instagram auto-sync completed. Total messages synced: {ig_synced}")

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
async def instagram_login(user_id: int = Query(...), workspace_id: Optional[int] = Query(None)):
    """Initiate Instagram OAuth flow"""
    ig_service = InstagramService()
    # Encode both user_id and workspace_id in state
    import json
    state_data = {"user_id": user_id, "workspace_id": workspace_id}
    auth_url = ig_service.get_oauth_url(state=json.dumps(state_data))
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

        # Parse state to get user_id and workspace_id
        import json
        user_id = None
        requested_workspace_id = None

        if state:
            try:
                # Try to parse as JSON (new format)
                state_data = json.loads(state)
                user_id = state_data.get("user_id")
                requested_workspace_id = state_data.get("workspace_id")
                logger.info(f"Parsed state: user_id={user_id}, workspace_id={requested_workspace_id}")
            except json.JSONDecodeError:
                # Fallback to old format (just user_id as string)
                user_id = int(state)
                logger.info(f"Legacy state format, user_id={user_id}")

        logger.info(f"Looking for user with ID: {user_id}")

        if not user_id:
            raise HTTPException(status_code=400, detail="User ID is required")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found with ID: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"User found: {user.username}")

        # Use requested workspace_id if provided, otherwise get/create default
        if requested_workspace_id:
            # Verify the workspace exists
            workspace = db.query(Workspace).filter(Workspace.id == requested_workspace_id).first()
            if workspace:
                workspace_id = requested_workspace_id
                logger.info(f"Using requested workspace {workspace_id}")
            else:
                workspace_id = get_or_create_default_workspace(user, db)
                logger.warning(f"Requested workspace {requested_workspace_id} not found, using default {workspace_id}")
        else:
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
                    # Different Instagram account - redirect with error (one Instagram per workspace)
                    logger.warning(f"Workspace {workspace_id} already has Instagram @{existing_workspace_instagram.platform_username}")
                    logger.warning(f"Cannot add Instagram @{ig_account.get('username')} (one Instagram per workspace)")
                    from app.config import settings
                    error_msg = f"This workspace already has Instagram @{existing_workspace_instagram.platform_username} connected. Disconnect it first to connect a different account."
                    redirect_url = f"{settings.FRONTEND_URL}/dashboard?error=instagram_conflict&message={error_msg}"
                    return RedirectResponse(url=redirect_url)

            # Check if this Instagram account is already connected to ANOTHER workspace
            # Check by both platform_user_id AND username (Instagram Business Login uses different IDs)
            from sqlalchemy import or_
            existing_other_workspace = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.is_active == True,
                    ConnectedAccount.workspace_id.isnot(None),
                    ConnectedAccount.workspace_id != workspace_id,
                )
                .filter(
                    or_(
                        ConnectedAccount.platform_user_id == instagram_account_id,
                        ConnectedAccount.platform_username == ig_account.get("username"),
                    )
                )
                .first()
            )

            if existing_other_workspace:
                logger.warning(f"Instagram account @{ig_account.get('username')} is already connected to workspace {existing_other_workspace.workspace_id}")
                from app.config import settings
                error_msg = f"Instagram @{ig_account.get('username')} is already connected to another workspace. Each Instagram account can only be in one workspace."
                redirect_url = f"{settings.FRONTEND_URL}/dashboard?error=instagram_in_use&message={error_msg}"
                return RedirectResponse(url=redirect_url)

            # Check if account already exists for this user IN THIS WORKSPACE
            existing_account_in_workspace = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.user_id == user.id,
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.workspace_id == workspace_id,
                )
                .filter(
                    or_(
                        ConnectedAccount.platform_user_id == instagram_account_id,
                        ConnectedAccount.platform_username == ig_account.get("username"),
                    )
                )
                .first()
            )

            # Also check if there's an INACTIVE account in any workspace (for migration)
            existing_account_any_workspace = (
                db.query(ConnectedAccount)
                .filter(
                    ConnectedAccount.user_id == user.id,
                    ConnectedAccount.platform == "instagram",
                    ConnectedAccount.is_active == False,  # Only check inactive accounts
                )
                .filter(
                    or_(
                        ConnectedAccount.platform_user_id == instagram_account_id,
                        ConnectedAccount.platform_username == ig_account.get("username"),
                    )
                )
                .first()
            )

            if existing_account_in_workspace:
                logger.info(f"Updating existing Instagram account ID: {existing_account_in_workspace.id} in workspace {workspace_id}")
                # Update existing account
                existing_account_in_workspace.access_token = access_token
                existing_account_in_workspace.platform_username = ig_account.get("username")
                # Store Instagram-scoped User ID for API calls
                existing_account_in_workspace.page_id = instagram_scoped_user_id
                existing_account_in_workspace.platform_user_id = instagram_account_id
                existing_account_in_workspace.connection_type = "instagram_business_login"
                existing_account_in_workspace.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in
                )
                existing_account_in_workspace.is_active = True
                existing_account_in_workspace.updated_at = datetime.utcnow()
            elif existing_account_any_workspace:
                # Found an INACTIVE account in another workspace - move it to new workspace
                old_workspace = existing_account_any_workspace.workspace_id
                logger.info(f"Moving inactive Instagram account from workspace {old_workspace} to workspace {workspace_id}")
                existing_account_any_workspace.workspace_id = workspace_id
                existing_account_any_workspace.access_token = access_token
                existing_account_any_workspace.platform_username = ig_account.get("username")
                existing_account_any_workspace.page_id = instagram_scoped_user_id
                existing_account_any_workspace.platform_user_id = instagram_account_id
                existing_account_any_workspace.connection_type = "instagram_business_login"
                existing_account_any_workspace.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in
                )
                existing_account_any_workspace.is_active = True
                existing_account_any_workspace.updated_at = datetime.utcnow()
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

        # IMPORTANT: Extract Instagram Account ID BEFORE syncing
        # Instagram Business Login provides two different IDs:
        # 1. Instagram-scoped User ID (from token exchange) - for API calls, stored in page_id
        # 2. Instagram Account ID (from conversation participants) - for webhooks AND message direction detection
        # We need the correct ID for message sync to work properly
        logger.info("🔍 Extracting Instagram Account ID from conversations BEFORE sync...")
        for ig_account in ig_accounts:
            try:
                account = (
                    db.query(ConnectedAccount)
                    .filter(
                        ConnectedAccount.user_id == user.id,
                        ConnectedAccount.platform == "instagram",
                        ConnectedAccount.workspace_id == workspace_id,
                    )
                    .first()
                )

                if account:
                    # Extract Instagram Account ID from conversation participants
                    real_instagram_account_id = await ig_service.extract_instagram_account_id_from_conversations(
                        instagram_scoped_user_id=instagram_user_id,
                        access_token=long_lived_token,
                        business_username=ig_account.get("username")
                    )

                    if real_instagram_account_id:
                        # Update platform_user_id with the correct Instagram Account ID
                        old_id = account.platform_user_id
                        account.platform_user_id = real_instagram_account_id
                        db.commit()
                        logger.info(f"✅ Updated platform_user_id BEFORE sync: {old_id} → {real_instagram_account_id}")
                        logger.info(f"✅ Account now ready for proper message direction detection!")
                    else:
                        logger.warning("⚠️  No conversations found - platform_user_id will remain as Instagram-scoped ID")
                        logger.info(f"ℹ️  Current platform_user_id: {account.platform_user_id}")

            except Exception as id_extract_error:
                logger.error(f"Failed to extract Instagram Account ID: {id_extract_error}")
                # Don't fail OAuth flow if ID extraction fails

        # Auto-sync conversations for all connected Instagram accounts
        # NOW the platform_user_id is correct for message direction detection
        logger.info("Starting auto-sync of Instagram conversations...")
        total_synced = 0
        for ig_account in ig_accounts:
            try:
                # Get the connected account we just created/updated (with correct platform_user_id)
                account = (
                    db.query(ConnectedAccount)
                    .filter(
                        ConnectedAccount.user_id == user.id,
                        ConnectedAccount.platform == "instagram",
                        ConnectedAccount.workspace_id == workspace_id,
                    )
                    .first()
                )

                if account:
                    logger.info(f"Syncing conversations for Instagram account {account.platform_user_id}...")
                    synced_count = await sync_account_messages(db, account)
                    total_synced += synced_count
                    logger.info(f"Synced {synced_count} messages from Instagram account")
            except Exception as sync_error:
                # Don't fail the OAuth flow if sync fails
                logger.error(f"Failed to auto-sync Instagram account: {sync_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

        logger.info(f"Auto-sync completed. Total messages synced: {total_synced}")

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
