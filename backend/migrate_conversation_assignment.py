"""
Migration script to add conversation assignment functionality.

This script:
1. Adds assigned_to_user_id column to conversation_participants table
2. Adds assigned_at column to conversation_participants table
3. Creates index for faster assignment queries

Run with: python backend/migrate_conversation_assignment.py
Or on Heroku: heroku run python backend/migrate_conversation_assignment.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from app.config import settings
from app.database import Base
from app.models import ConversationParticipant


def run_migration():
    """Run the database migration"""
    print("🚀 Starting conversation assignment migration...")

    # Create engine
    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()

            try:
                print("\n📊 Step 1: Adding assigned_to_user_id column...")

                # Add assigned_to_user_id column
                try:
                    conn.execute(text("""
                        ALTER TABLE conversation_participants
                        ADD COLUMN IF NOT EXISTS assigned_to_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
                    """))
                    print("✅ Added assigned_to_user_id column")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        raise
                    print("ℹ️  assigned_to_user_id column already exists")

                print("\n📊 Step 2: Adding assigned_at column...")

                # Add assigned_at column
                try:
                    conn.execute(text("""
                        ALTER TABLE conversation_participants
                        ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP
                    """))
                    print("✅ Added assigned_at column")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        raise
                    print("ℹ️  assigned_at column already exists")

                print("\n📊 Step 3: Creating indexes for performance...")

                # Create indexes
                indexes = [
                    ("idx_conv_participants_assigned", "CREATE INDEX IF NOT EXISTS idx_conv_participants_assigned ON conversation_participants(assigned_to_user_id) WHERE assigned_to_user_id IS NOT NULL"),
                    ("idx_conv_participants_workspace_assigned", "CREATE INDEX IF NOT EXISTS idx_conv_participants_workspace_assigned ON conversation_participants(workspace_id, assigned_to_user_id)"),
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
                print("  - Added assigned_to_user_id column")
                print("  - Added assigned_at column")
                print("  - Created performance indexes")

            except Exception as e:
                trans.rollback()
                print(f"\n❌ Migration failed: {e}")
                raise

    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
