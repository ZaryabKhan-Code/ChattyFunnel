"""
Migration script to add new fields to messages table and create conversation_participants table
Run this once on Heroku: python migrate_add_message_fields.py
"""
import os
from sqlalchemy import create_engine, text, inspect

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Fix postgres:// to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

print("🔄 Starting database migration...")

with engine.connect() as conn:
    # Check if columns already exist
    columns = [col['name'] for col in inspector.get_columns('messages')]
    print(f"📋 Current columns in messages table: {columns}")

    # Add message_type column if it doesn't exist
    if 'message_type' not in columns:
        print("➕ Adding message_type column...")
        conn.execute(text("""
            ALTER TABLE messages
            ADD COLUMN message_type VARCHAR(50) DEFAULT 'text' NOT NULL
        """))
        conn.commit()
        print("✅ Added message_type column")
    else:
        print("⏭️  message_type column already exists")

    # Make content nullable
    print("🔧 Making content column nullable...")
    conn.execute(text("""
        ALTER TABLE messages
        ALTER COLUMN content DROP NOT NULL
    """))
    conn.commit()
    print("✅ Content column is now nullable")

    # Add attachment columns if they don't exist
    attachment_columns = {
        'attachment_url': 'VARCHAR(500)',
        'attachment_type': 'VARCHAR(50)',
        'attachment_filename': 'VARCHAR(255)',
        'thumbnail_url': 'VARCHAR(500)'
    }

    for col_name, col_type in attachment_columns.items():
        if col_name not in columns:
            print(f"➕ Adding {col_name} column...")
            conn.execute(text(f"""
                ALTER TABLE messages
                ADD COLUMN {col_name} {col_type}
            """))
            conn.commit()
            print(f"✅ Added {col_name} column")
        else:
            print(f"⏭️  {col_name} column already exists")

    # Create conversation_participants table if it doesn't exist
    if 'conversation_participants' not in inspector.get_table_names():
        print("➕ Creating conversation_participants table...")
        conn.execute(text("""
            CREATE TABLE conversation_participants (
                id SERIAL PRIMARY KEY,
                conversation_id VARCHAR(255) NOT NULL,
                platform VARCHAR(50) NOT NULL,
                platform_conversation_id VARCHAR(255),
                participant_id VARCHAR(255) NOT NULL,
                participant_name VARCHAR(255),
                participant_username VARCHAR(255),
                participant_profile_pic VARCHAR(500),
                user_id INTEGER NOT NULL,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))
        conn.commit()

        # Create index on conversation_id
        conn.execute(text("""
            CREATE INDEX ix_conversation_participants_conversation_id
            ON conversation_participants(conversation_id)
        """))
        conn.commit()

        # Create index on user_id
        conn.execute(text("""
            CREATE INDEX ix_conversation_participants_user_id
            ON conversation_participants(user_id)
        """))
        conn.commit()

        print("✅ Created conversation_participants table with indexes")
    else:
        print("⏭️  conversation_participants table already exists")

        # Add ai_enabled column to existing conversation_participants table
        conv_columns = [col['name'] for col in inspector.get_columns('conversation_participants')]
        if 'ai_enabled' not in conv_columns:
            print("➕ Adding ai_enabled column to conversation_participants...")
            conn.execute(text("""
                ALTER TABLE conversation_participants
                ADD COLUMN ai_enabled BOOLEAN DEFAULT FALSE NOT NULL
            """))
            conn.commit()
            print("✅ Added ai_enabled column")
        else:
            print("⏭️  ai_enabled column already exists")

    # Create ai_settings table if it doesn't exist
    if 'ai_settings' not in inspector.get_table_names():
        print("➕ Creating ai_settings table...")
        conn.execute(text("""
            CREATE TABLE ai_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                ai_provider VARCHAR(50) DEFAULT 'openai' NOT NULL,
                api_key VARCHAR(500),
                model_name VARCHAR(100) DEFAULT 'gpt-4' NOT NULL,
                system_prompt TEXT,
                response_tone VARCHAR(50) DEFAULT 'professional' NOT NULL,
                max_tokens INTEGER DEFAULT 500 NOT NULL,
                temperature INTEGER DEFAULT 7 NOT NULL,
                context_messages_count INTEGER DEFAULT 10 NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))
        conn.commit()
        print("✅ Created ai_settings table")
    else:
        print("⏭️  ai_settings table already exists")

print("🎉 Migration completed successfully!")
print("\n📝 Next steps:")
print("   1. Restart your Heroku dyno if needed: heroku restart")
print("   2. Try syncing messages again from the frontend")
print("   3. Configure AI settings via /api/ai/settings endpoint")
