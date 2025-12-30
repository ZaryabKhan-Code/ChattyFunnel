# Workspace, Funnel & AI Bot System Design

## 🎯 Overview

This document outlines the architecture for workspaces, funnels, AI bots, and enhanced messaging features.

## 📊 Database Schema

### 1. Workspaces Table
```sql
CREATE TABLE workspaces (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** Organize accounts and conversations into isolated workspaces
**Key Features:**
- Multi-workspace support per user
- Owner can manage workspace settings
- Soft delete with is_active flag

### 2. Workspace Members Table
```sql
CREATE TABLE workspace_members (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member', -- owner, admin, member
    permissions JSONB DEFAULT '{}', -- Custom permissions
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(workspace_id, user_id)
);
```

**Purpose:** Multi-user collaboration within workspaces
**Roles:**
- `owner`: Full control
- `admin`: Manage members, funnels, bots
- `member`: View and interact with conversations

### 3. Connected Accounts - UPDATE
```sql
ALTER TABLE connected_accounts
ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL,
ADD COLUMN is_workspace_exclusive BOOLEAN DEFAULT FALSE;

CREATE UNIQUE INDEX idx_exclusive_accounts
ON connected_accounts (platform, platform_user_id)
WHERE is_workspace_exclusive = TRUE;
```

**Purpose:** Link accounts to workspaces with exclusivity
**Logic:**
- If `is_workspace_exclusive = TRUE`, account can only exist in ONE workspace globally
- Prevents duplicate connections across different users

### 4. Funnels Table
```sql
CREATE TABLE funnels (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    trigger_type VARCHAR(50) NOT NULL, -- keyword, new_conversation, tag, custom
    trigger_config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0, -- Higher priority funnels run first
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** Automated conversation flows and marketing sequences
**Trigger Types:**
- `keyword`: Message contains specific keywords
- `new_conversation`: New user starts conversation
- `tag`: User has specific tag
- `custom`: Custom JavaScript condition

### 5. Funnel Steps Table
```sql
CREATE TABLE funnel_steps (
    id SERIAL PRIMARY KEY,
    funnel_id INTEGER NOT NULL REFERENCES funnels(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    step_order INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL, -- send_message, delay, condition, tag, assign_human, ai_response
    step_config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(funnel_id, step_order)
);
```

**Purpose:** Define sequence of actions in a funnel
**Step Types:**
- `send_message`: Send automated message
- `delay`: Wait X minutes/hours/days
- `condition`: Branch based on user response
- `tag`: Add/remove tags from user
- `assign_human`: Exit automation, notify human
- `ai_response`: Let AI bot respond

**Example Funnel Flow:**
```json
{
  "funnel_name": "Welcome Sequence",
  "steps": [
    {"order": 1, "type": "send_message", "config": {"text": "Hi! Thanks for reaching out!"}},
    {"order": 2, "type": "delay", "config": {"minutes": 5}},
    {"order": 3, "type": "ai_response", "config": {"bot_id": 123, "max_messages": 3}},
    {"order": 4, "type": "condition", "config": {
      "if": "user_replied",
      "then": "continue",
      "else": "assign_human"
    }},
    {"order": 5, "type": "tag", "config": {"add": ["engaged"], "remove": ["cold"]}}
  ]
}
```

### 6. Conversation Tags Table
```sql
CREATE TABLE conversation_tags (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    conversation_id VARCHAR(255) NOT NULL,
    tag VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(conversation_id, tag)
);
```

**Purpose:** Tag conversations for segmentation and funnel triggers

### 7. Funnel Enrollments Table
```sql
CREATE TABLE funnel_enrollments (
    id SERIAL PRIMARY KEY,
    funnel_id INTEGER NOT NULL REFERENCES funnels(id) ON DELETE CASCADE,
    conversation_id VARCHAR(255) NOT NULL,
    current_step INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'active', -- active, completed, paused, exited
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    next_step_at TIMESTAMP, -- When to execute next step
    metadata JSONB DEFAULT '{}',
    UNIQUE(funnel_id, conversation_id, status)
);
```

**Purpose:** Track which conversations are in which funnels and their progress

### 8. AI Bots Table
```sql
CREATE TABLE ai_bots (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    bot_type VARCHAR(50) NOT NULL, -- workspace_default, funnel_specific, conversation_override

    -- Bot configuration
    ai_provider VARCHAR(50) DEFAULT 'openai', -- openai, anthropic, custom
    ai_model VARCHAR(100) DEFAULT 'gpt-4',
    system_prompt TEXT NOT NULL,
    temperature DECIMAL(3,2) DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 500,

    -- Behavior settings
    auto_respond BOOLEAN DEFAULT FALSE,
    response_delay_seconds INTEGER DEFAULT 0,
    max_messages_per_conversation INTEGER, -- NULL = unlimited

    -- Training data
    knowledge_base_url TEXT,
    context_window_messages INTEGER DEFAULT 10,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** AI-powered automated responses
**Bot Types:**
1. `workspace_default`: Default bot for all conversations in workspace
2. `funnel_specific`: Bot activated during specific funnel steps
3. `conversation_override`: Manual bot assignment to specific conversations

### 9. AI Bot Triggers Table
```sql
CREATE TABLE ai_bot_triggers (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES ai_bots(id) ON DELETE CASCADE,
    trigger_type VARCHAR(50) NOT NULL, -- keyword, sentiment, time_based, always
    trigger_config JSONB NOT NULL DEFAULT '{}',
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);
```

**Purpose:** Define when bots should respond
**Examples:**
```json
// Keyword trigger
{"type": "keyword", "config": {"keywords": ["price", "cost", "how much"], "match": "any"}}

// Sentiment trigger
{"type": "sentiment", "config": {"sentiment": "negative", "threshold": 0.7}}

// Time-based trigger
{"type": "time_based", "config": {"between": "09:00-17:00", "timezone": "UTC"}}

// Always respond
{"type": "always", "config": {}}
```

### 10. Conversation AI Settings Table
```sql
CREATE TABLE conversation_ai_settings (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL UNIQUE,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    ai_enabled BOOLEAN DEFAULT FALSE,
    assigned_bot_id INTEGER REFERENCES ai_bots(id) ON DELETE SET NULL,
    funnel_id INTEGER REFERENCES funnels(id) ON DELETE SET NULL, -- Current funnel
    override_workspace_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** Per-conversation AI settings and overrides

### 11. Message Attachments Table
```sql
CREATE TABLE message_attachments (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    attachment_type VARCHAR(50) NOT NULL, -- image, video, audio, voice_note, file
    file_url TEXT NOT NULL,
    file_name VARCHAR(255),
    file_size INTEGER, -- bytes
    mime_type VARCHAR(100),
    duration INTEGER, -- For audio/video in seconds

    -- Voice note specific
    is_voice_note BOOLEAN DEFAULT FALSE,
    transcription TEXT, -- AI transcription

    -- Storage metadata
    storage_provider VARCHAR(50) DEFAULT 'local', -- local, s3, cloudinary
    storage_path TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** Handle all message attachments including voice notes

## 🤖 AI Bot Architecture Recommendation

### Recommended Approach: **Hierarchical AI Bot System**

```
Priority Order (highest to lowest):
1. Conversation Override Bot (manual assignment)
2. Funnel-Specific Bot (active funnel step)
3. Workspace Default Bot (fallback)
```

**How It Works:**

1. **New message arrives** →
2. **Check if conversation has override bot assigned** →
   - Yes? Use that bot
   - No? Continue
3. **Check if conversation is in active funnel** →
   - Yes? Check if current step is `ai_response` type
     - Yes? Use funnel's assigned bot
     - No? Skip AI response
   - No? Continue
4. **Check workspace default bot** →
   - Enabled? Use workspace default bot
   - Disabled? No AI response

**Benefits:**
- ✅ Flexible: Support all use cases (global, funnel, individual)
- ✅ Scalable: Easy to add new bot types
- ✅ Override-friendly: Manual control when needed
- ✅ Funnel-integrated: AI works within automated sequences

## 📁 File Structure

```
backend/
├── app/
│   ├── models/
│   │   ├── workspace.py (new)
│   │   ├── funnel.py (new)
│   │   ├── ai_bot.py (new)
│   │   └── message_attachment.py (new)
│   ├── routers/
│   │   ├── workspaces.py (new)
│   │   ├── funnels.py (new)
│   │   ├── ai_bots.py (new)
│   │   └── attachments.py (new)
│   ├── services/
│   │   ├── workspace_service.py (new)
│   │   ├── funnel_service.py (new)
│   │   ├── ai_bot_service.py (new)
│   │   └── attachment_service.py (new)
│   └── schemas/
│       ├── workspace.py (new)
│       ├── funnel.py (new)
│       └── ai_bot.py (new)

frontend/
├── app/
│   ├── workspaces/
│   │   ├── page.tsx (workspace list)
│   │   ├── [workspace_id]/
│   │   │   ├── page.tsx (workspace dashboard)
│   │   │   ├── settings/page.tsx
│   │   │   ├── funnels/page.tsx
│   │   │   └── ai-bots/page.tsx
│   ├── components/
│   │   ├── workspace/
│   │   │   ├── WorkspaceSelector.tsx
│   │   │   ├── WorkspaceMembers.tsx
│   │   │   └── AccountManager.tsx
│   │   ├── funnel/
│   │   │   ├── FunnelBuilder.tsx
│   │   │   ├── FunnelStepEditor.tsx
│   │   │   └── FunnelAnalytics.tsx
│   │   ├── ai-bot/
│   │   │   ├── BotConfigurator.tsx
│   │   │   ├── BotTriggerEditor.tsx
│   │   │   └── BotTester.tsx
│   │   └── message/
│   │       ├── VoiceNoteRecorder.tsx
│   │       ├── AttachmentUploader.tsx
│   │       └── MessageInput.tsx (updated)
```

## 🔒 Account Exclusivity Logic

### Rule:
If an account is marked as `is_workspace_exclusive = TRUE`, it can only be connected to ONE workspace globally.

### Implementation:

1. **During OAuth Callback:**
   ```python
   # Check if account already exists in another workspace
   existing = db.query(ConnectedAccount).filter(
       ConnectedAccount.platform == platform,
       ConnectedAccount.platform_user_id == platform_user_id,
       ConnectedAccount.is_workspace_exclusive == True
   ).first()

   if existing:
       raise HTTPException(
           status_code=409,
           detail=f"This {platform} account is already connected to another workspace"
       )
   ```

2. **When Adding Account to Workspace:**
   - User can choose: "Make this account exclusive to this workspace"
   - If selected, set `is_workspace_exclusive = TRUE`
   - Database unique constraint prevents duplicates

3. **Frontend Warning:**
   - Show warning: "This account is exclusive to [Workspace Name]"
   - Provide option to disconnect from other workspace first

## 🎙️ Voice Notes & Attachments

### Features:
1. **Voice Note Recording:**
   - Browser MediaRecorder API
   - Real-time waveform visualization
   - Max duration: 5 minutes
   - Format: WebM/Opus

2. **File Attachments:**
   - Images: PNG, JPG, GIF (max 10MB)
   - Videos: MP4, MOV (max 50MB)
   - Documents: PDF, DOCX (max 25MB)

3. **Upload Flow:**
   ```
   User selects/records → Upload to storage → Get URL → Send via API → Save to database
   ```

4. **Storage Options:**
   - Development: Local filesystem
   - Production: S3/Cloudinary

## 📊 Example User Flows

### Flow 1: Setting Up a Workspace
1. User creates workspace "E-commerce Store"
2. Connects Instagram account (marks as exclusive)
3. Creates funnel "New Customer Welcome"
4. Sets up workspace default AI bot
5. Invites team members

### Flow 2: Customer Interaction
1. New message arrives from Instagram
2. System checks: No active funnel enrollment
3. Funnel trigger matches (keyword: "price")
4. Enroll in "Product Inquiry" funnel
5. Step 1: Send product catalog
6. Step 2: Wait 2 minutes
7. Step 3: AI bot responds to questions (max 5 messages)
8. Step 4: If no response in 10 min → Assign to human

### Flow 3: Voice Note Handling
1. User receives voice note
2. Backend downloads audio file
3. Save to message_attachments table
4. (Optional) Transcribe using Whisper API
5. Display in frontend with play button + transcription

## ❓ Questions for You

Before I start implementing, please confirm:

1. **AI Bot Preference:** Do you agree with the hierarchical approach (Conversation Override > Funnel Bot > Workspace Default)?

2. **Storage:** Where should attachments be stored?
   - Local filesystem (simple, for development)
   - AWS S3 (scalable, production-ready)
   - Cloudinary (easy, includes transformations)

3. **Voice Note Transcription:** Should voice notes be auto-transcribed?
   - If yes, which service? (OpenAI Whisper, Google Speech-to-Text, etc.)

4. **Workspace Collaboration:** Do you want multi-user workspaces now, or start with single-user and add later?

5. **Funnel Builder UI:** Should it be:
   - Simple form-based (quick to build)
   - Visual drag-and-drop flowchart (more complex, better UX)

Please review and let me know your preferences! I'll then start implementing based on your decisions.
