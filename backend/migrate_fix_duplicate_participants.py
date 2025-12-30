"""
Migration script to fix duplicate conversation_participants records.

This script:
1. Identifies duplicate records (same conversation_id, workspace_id)
2. Keeps only the most recent record (highest id) for each duplicate group
3. Deletes the older duplicate records
4. Adds a unique constraint to prevent future duplicates

Run with: python backend/migrate_fix_duplicate_participants.py
Or on Heroku: heroku run python backend/migrate_fix_duplicate_participants.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from app.config import settings


def run_migration():
    """Run the database migration"""
    print("🚀 Starting duplicate conversation_participants cleanup migration...")

    # Create engine
    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()

            try:
                print("\n📊 Step 1: Analyzing duplicate records...")

                # Find duplicates (same conversation_id and workspace_id)
                result = conn.execute(text("""
                    SELECT conversation_id, workspace_id, COUNT(*) as cnt
                    FROM conversation_participants
                    WHERE workspace_id IS NOT NULL
                    GROUP BY conversation_id, workspace_id
                    HAVING COUNT(*) > 1
                """))
                duplicates = result.fetchall()

                if not duplicates:
                    print("✅ No duplicate records found!")
                else:
                    print(f"⚠️  Found {len(duplicates)} groups of duplicate records")

                    # For each duplicate group, keep only the one with the highest ID (most recent)
                    total_deleted = 0
                    for conv_id, workspace_id, count in duplicates:
                        # Get all IDs for this duplicate group
                        ids_result = conn.execute(text("""
                            SELECT id FROM conversation_participants
                            WHERE conversation_id = :conv_id
                            AND (workspace_id = :workspace_id OR (:workspace_id IS NULL AND workspace_id IS NULL))
                            ORDER BY id DESC
                        """), {"conv_id": conv_id, "workspace_id": workspace_id})
                        all_ids = [row[0] for row in ids_result.fetchall()]

                        if len(all_ids) > 1:
                            # Keep the first one (highest ID), delete the rest
                            keep_id = all_ids[0]
                            delete_ids = all_ids[1:]

                            # Delete duplicates
                            conn.execute(text("""
                                DELETE FROM conversation_participants
                                WHERE id = ANY(:delete_ids)
                            """), {"delete_ids": delete_ids})

                            total_deleted += len(delete_ids)
                            print(f"  🗑️  Deleted {len(delete_ids)} duplicates for conversation {conv_id}, kept ID {keep_id}")

                    print(f"\n✅ Deleted {total_deleted} duplicate records total")

                print("\n📊 Step 2: Checking for NULL workspace duplicates...")

                # Also handle records where workspace_id is NULL
                result = conn.execute(text("""
                    SELECT conversation_id, COUNT(*) as cnt
                    FROM conversation_participants
                    WHERE workspace_id IS NULL
                    GROUP BY conversation_id
                    HAVING COUNT(*) > 1
                """))
                null_duplicates = result.fetchall()

                if null_duplicates:
                    print(f"⚠️  Found {len(null_duplicates)} groups of NULL workspace duplicates")
                    for conv_id, count in null_duplicates:
                        ids_result = conn.execute(text("""
                            SELECT id FROM conversation_participants
                            WHERE conversation_id = :conv_id
                            AND workspace_id IS NULL
                            ORDER BY id DESC
                        """), {"conv_id": conv_id})
                        all_ids = [row[0] for row in ids_result.fetchall()]

                        if len(all_ids) > 1:
                            keep_id = all_ids[0]
                            delete_ids = all_ids[1:]

                            conn.execute(text("""
                                DELETE FROM conversation_participants
                                WHERE id = ANY(:delete_ids)
                            """), {"delete_ids": delete_ids})

                            print(f"  🗑️  Deleted {len(delete_ids)} NULL workspace duplicates for conversation {conv_id}")
                else:
                    print("✅ No NULL workspace duplicates found")

                print("\n📊 Step 3: Adding unique constraint...")

                # Try to add unique constraint (will fail if already exists)
                try:
                    conn.execute(text("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_participants_unique
                        ON conversation_participants(conversation_id, workspace_id)
                        WHERE workspace_id IS NOT NULL
                    """))
                    print("✅ Created unique index idx_conversation_participants_unique")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print("ℹ️  Unique index already exists")
                    else:
                        raise

                # Also create index for NULL workspace_id (single conversation per NULL workspace)
                try:
                    conn.execute(text("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_participants_unique_null_ws
                        ON conversation_participants(conversation_id)
                        WHERE workspace_id IS NULL
                    """))
                    print("✅ Created unique index idx_conversation_participants_unique_null_ws")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print("ℹ️  NULL workspace unique index already exists")
                    else:
                        raise

                # Commit transaction
                trans.commit()
                print("\n✅ Migration completed successfully!")

                # Print summary
                result = conn.execute(text("SELECT COUNT(*) FROM conversation_participants"))
                remaining_count = result.fetchone()[0]
                print(f"\n📊 Summary:")
                print(f"  - Remaining conversation_participants: {remaining_count}")
                print(f"  - Unique constraints added to prevent future duplicates")

            except Exception as e:
                trans.rollback()
                print(f"\n❌ Migration failed: {e}")
                raise

    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
