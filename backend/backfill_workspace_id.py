"""
Backfill workspace_id for existing conversation_participants
This script updates all conversation participants that have NULL workspace_id
by looking up the workspace_id from their connected account
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import ConversationParticipant, ConnectedAccount
from sqlalchemy import and_

def backfill_workspace_ids():
    db = SessionLocal()
    try:
        # Get all conversation participants with NULL workspace_id
        participants = db.query(ConversationParticipant).filter(
            ConversationParticipant.workspace_id.is_(None)
        ).all()

        print(f"Found {len(participants)} conversation participants with NULL workspace_id")

        updated_count = 0
        for participant in participants:
            # Find the connected account for this user to get workspace_id
            # Try to match by user_id and platform
            connected_account = db.query(ConnectedAccount).filter(
                and_(
                    ConnectedAccount.user_id == participant.user_id,
                    ConnectedAccount.platform == participant.platform,
                    ConnectedAccount.is_active == True
                )
            ).first()

            if connected_account and connected_account.workspace_id:
                participant.workspace_id = connected_account.workspace_id
                updated_count += 1
                print(f"Updated conversation {participant.conversation_id} -> workspace {connected_account.workspace_id}")

        db.commit()
        print(f"\n✅ Successfully updated {updated_count} conversation participants")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting workspace_id backfill...")
    backfill_workspace_ids()
    print("Done!")
