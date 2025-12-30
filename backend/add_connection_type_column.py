"""
Database migration: Add connection_type column to connected_accounts table

This migration adds a connection_type column to track whether an Instagram account
is connected via:
- 'facebook_page' (uses graph.facebook.com)
- 'instagram_business_login' (uses graph.instagram.com)

Run this on Heroku:
heroku run python backend/add_connection_type_column.py --app roamifly-admin-b97e90c67026
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
    print("📋 Adding connection_type column...")

    # Check if column already exists
    check_query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='connected_accounts'
        AND column_name='connection_type';
    """)

    result = session.execute(check_query).fetchone()

    if result:
        print("ℹ️  connection_type column already exists")
    else:
        # Add the column
        add_column_query = text("""
            ALTER TABLE connected_accounts
            ADD COLUMN connection_type VARCHAR(50);
        """)

        session.execute(add_column_query)
        session.commit()
        print("✅ Added connection_type column")

    # Auto-populate connection_type based on access token
    print("🔧 Auto-populating connection_type for existing accounts...")

    update_query = text("""
        UPDATE connected_accounts
        SET connection_type = CASE
            WHEN platform = 'facebook' THEN NULL
            WHEN platform = 'instagram' AND access_token LIKE 'IGAAL%' THEN 'instagram_business_login'
            WHEN platform = 'instagram' AND access_token LIKE 'EAA%' THEN 'facebook_page'
            ELSE NULL
        END
        WHERE connection_type IS NULL;
    """)

    result = session.execute(update_query)
    session.commit()

    print(f"✅ Updated {result.rowcount} accounts")

    # Show the current state
    print("\n📊 Current Instagram accounts:")
    query = text("""
        SELECT id, user_id, platform, connection_type, platform_username,
               LEFT(access_token, 10) as token_prefix
        FROM connected_accounts
        WHERE platform = 'instagram'
        ORDER BY id;
    """)

    accounts = session.execute(query).fetchall()

    for account in accounts:
        print(f"  ID {account[0]}: @{account[4]} - {account[2]} ({account[3]}) - Token: {account[5]}...")

    print("\n✅ Migration complete!")

except Exception as e:
    print(f"❌ Error: {e}")
    session.rollback()
    raise
finally:
    session.close()
