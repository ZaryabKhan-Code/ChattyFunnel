"""
Fix Instagram Business Login account IDs in database.

This script updates existing Instagram Business Login accounts to use the correct ID mapping:
- platform_user_id = Instagram Account ID (for webhooks)
- page_id = Instagram-scoped User ID (for API calls)

Run this ONCE after deploying the new OAuth code.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL environment variable not set")
    exit(1)

# Fix for Heroku postgres:// -> postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"🔌 Connecting to database...")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

try:
    # Find Instagram Business Login accounts (IGAAL tokens)
    print("🔍 Finding Instagram Business Login accounts...")

    query = text("""
        SELECT id, user_id, platform_user_id, page_id, platform_username, access_token
        FROM connected_accounts
        WHERE platform = 'instagram'
        AND access_token LIKE 'IGAAL%'
    """)

    accounts = session.execute(query).fetchall()

    if not accounts:
        print("ℹ️  No Instagram Business Login accounts found")
        session.close()
        exit(0)

    print(f"📊 Found {len(accounts)} Instagram Business Login account(s)")

    for account in accounts:
        account_id, user_id, platform_user_id, page_id, username, token = account

        print(f"\n{'='*80}")
        print(f"Account ID: {account_id}")
        print(f"User ID: {user_id}")
        print(f"Username: @{username}")
        print(f"Current platform_user_id: {platform_user_id}")
        print(f"Current page_id: {page_id}")

        # For Instagram Business Login, these should be DIFFERENT
        # platform_user_id = Instagram Account ID (from /me endpoint, for webhooks)
        # page_id = Instagram-scoped User ID (from token exchange, for API calls)

        # If they're the same, we need to fetch the correct Instagram Account ID
        if platform_user_id == page_id:
            print("⚠️  IDs are the same - need to fetch Instagram Account ID from API")

            # Fetch Instagram Account ID from /me endpoint
            import httpx
            import asyncio

            async def get_instagram_account_id(access_token):
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://graph.instagram.com/me",
                        params={
                            "fields": "id",
                            "access_token": access_token,
                        },
                    )
                    if response.status_code == 200:
                        return response.json().get("id")
                    return None

            instagram_account_id = asyncio.run(get_instagram_account_id(token))

            if instagram_account_id:
                print(f"✅ Fetched Instagram Account ID: {instagram_account_id}")

                # Update the database
                update_query = text("""
                    UPDATE connected_accounts
                    SET platform_user_id = :instagram_account_id
                    WHERE id = :account_id
                """)

                session.execute(update_query, {
                    "instagram_account_id": instagram_account_id,
                    "account_id": account_id
                })

                print(f"✅ Updated account {account_id}:")
                print(f"   platform_user_id: {platform_user_id} → {instagram_account_id}")
                print(f"   page_id: {page_id} (unchanged - correct for API calls)")
            else:
                print(f"❌ Failed to fetch Instagram Account ID for account {account_id}")
        else:
            print("✅ IDs are already different - no update needed")

    session.commit()
    print(f"\n{'='*80}")
    print("✅ Database update complete!")

except Exception as e:
    print(f"❌ Error: {e}")
    session.rollback()
    raise
finally:
    session.close()
