"""
Migration script to add workspace, funnel, AI bot, and attachment system.

This script:
1. Creates new tables for workspaces, funnels, AI bots, and attachments
2. Adds workspace_id and is_workspace_exclusive columns to connected_accounts
3. Creates a default workspace for existing users
4. Assigns existing accounts to default workspaces

Run with: python backend/migrate_workspace_system.py
Or on Heroku: heroku run python backend/migrate_workspace_system.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from app.config import settings
from app.database import Base
from app.models import (
    User,
    Workspace,
    WorkspaceMember,
    ConnectedAccount,
    Funnel,
    FunnelStep,
    FunnelEnrollment,
    AIBot,
    AIBotTrigger,
    ConversationAISettings,
    ConversationTag,
    MessageAttachment,
)


def run_migration():
    """Run the database migration"""
    print("🚀 Starting workspace system migration...")

    # Create engine
    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()

            try:
                print("\n📊 Step 1: Creating new tables...")

                # Create all new tables
                Base.metadata.create_all(bind=engine, checkfirst=True)
                print("✅ All tables created/verified")

                print("\n📊 Step 2: Adding columns to connected_accounts...")

                # Add workspace_id column
                try:
                    conn.execute(text("""
                        ALTER TABLE connected_accounts
                        ADD COLUMN IF NOT EXISTS workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL
                    """))
                    print("✅ Added workspace_id column")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        raise
                    print("ℹ️  workspace_id column already exists")

                # Add is_workspace_exclusive column
                try:
                    conn.execute(text("""
                        ALTER TABLE connected_accounts
                        ADD COLUMN IF NOT EXISTS is_workspace_exclusive BOOLEAN DEFAULT FALSE
                    """))
                    print("✅ Added is_workspace_exclusive column")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        raise
                    print("ℹ️  is_workspace_exclusive column already exists")

                print("\n📊 Step 3: Creating default workspaces for existing users...")

                # Get all users
                result = conn.execute(text("SELECT id, username FROM users"))
                users = result.fetchall()

                print(f"Found {len(users)} users")

                for user_id, username in users:
                    # Check if user already has a workspace
                    result = conn.execute(
                        text("SELECT id FROM workspaces WHERE owner_id = :owner_id LIMIT 1"),
                        {"owner_id": user_id}
                    )
                    existing_workspace = result.fetchone()

                    if existing_workspace:
                        workspace_id = existing_workspace[0]
                        print(f"  ℹ️  User {username} (ID: {user_id}) already has workspace {workspace_id}")
                    else:
                        # Create default workspace
                        result = conn.execute(
                            text("""
                                INSERT INTO workspaces (owner_id, name, description, is_active, created_at, updated_at)
                                VALUES (:owner_id, :name, :description, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                RETURNING id
                            """),
                            {
                                "owner_id": user_id,
                                "name": f"{username}'s Workspace",
                                "description": "Default workspace"
                            }
                        )
                        workspace_id = result.fetchone()[0]
                        print(f"  ✅ Created workspace {workspace_id} for user {username} (ID: {user_id})")

                        # Add owner as workspace member
                        conn.execute(
                            text("""
                                INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
                                VALUES (:workspace_id, :user_id, 'owner', CURRENT_TIMESTAMP)
                            """),
                            {
                                "workspace_id": workspace_id,
                                "user_id": user_id
                            }
                        )

                    # Assign all user's connected accounts to their default workspace
                    result = conn.execute(
                        text("""
                            UPDATE connected_accounts
                            SET workspace_id = :workspace_id
                            WHERE user_id = :user_id AND workspace_id IS NULL
                        """),
                        {
                            "workspace_id": workspace_id,
                            "user_id": user_id
                        }
                    )
                    updated_count = result.rowcount
                    if updated_count > 0:
                        print(f"  ✅ Assigned {updated_count} connected accounts to workspace {workspace_id}")

                print("\n📊 Step 4: Creating indexes for performance...")

                # Create indexes
                indexes = [
                    ("idx_workspace_members_unique", "CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_members_unique ON workspace_members(workspace_id, user_id)"),
                    ("idx_conversation_tags_unique", "CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_tags_unique ON conversation_tags(conversation_id, tag)"),
                    ("idx_funnel_steps_unique", "CREATE UNIQUE INDEX IF NOT EXISTS idx_funnel_steps_unique ON funnel_steps(funnel_id, step_order)"),
                    ("idx_funnel_enrollments_unique", "CREATE UNIQUE INDEX IF NOT EXISTS idx_funnel_enrollments_unique ON funnel_enrollments(funnel_id, conversation_id, status)"),
                    ("idx_conversation_ai_settings_conv", "CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_ai_settings_conv ON conversation_ai_settings(conversation_id)"),
                    ("idx_connected_accounts_workspace", "CREATE INDEX IF NOT EXISTS idx_connected_accounts_workspace ON connected_accounts(workspace_id)"),
                    ("idx_funnel_enrollments_next_step", "CREATE INDEX IF NOT EXISTS idx_funnel_enrollments_next_step ON funnel_enrollments(next_step_at) WHERE status = 'active'"),
                ]

                for idx_name, idx_sql in indexes:
                    try:
                        conn.execute(text(idx_sql))
                        print(f"  ✅ Created index: {idx_name}")
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            raise
                        print(f"  ℹ️  Index {idx_name} already exists")

                # Commit transaction
                trans.commit()
                print("\n✅ Migration completed successfully!")
                print("\n📊 Summary:")
                print(f"  - Created {len(users)} default workspaces")
                print(f"  - All tables and indexes created")
                print(f"  - Existing accounts assigned to workspaces")

            except Exception as e:
                trans.rollback()
                print(f"\n❌ Migration failed: {e}")
                raise

    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
