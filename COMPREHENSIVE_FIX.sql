-- ========================================================================
-- COMPREHENSIVE FIX FOR INSTAGRAM ACCOUNTS
-- ========================================================================
-- This script fixes all Instagram connection issues in one go.
-- Run on Heroku: heroku pg:psql --app roamifly-admin-b97e90c67026
-- ========================================================================

-- Step 1: Add connection_type column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='connected_accounts' AND column_name='connection_type'
    ) THEN
        ALTER TABLE connected_accounts ADD COLUMN connection_type VARCHAR(50);
        RAISE NOTICE 'Added connection_type column';
    ELSE
        RAISE NOTICE 'connection_type column already exists';
    END IF;
END $$;

-- Step 2: Show current state
SELECT id, user_id, platform, connection_type, platform_user_id, page_id, platform_username,
       LEFT(access_token, 10) as token_prefix
FROM connected_accounts
WHERE platform = 'instagram'
ORDER BY id;

-- Step 3: Fix account 5 (Instagram Business Login)
-- Set platform_user_id to Instagram Account ID (for webhooks)
UPDATE connected_accounts
SET
    platform_user_id = '17841479846631738',  -- Instagram Account ID from /me
    connection_type = 'instagram_business_login'
WHERE id = 5;

-- Step 4: Fix account 2 (Facebook Page-managed Instagram)
UPDATE connected_accounts
SET connection_type = 'facebook_page'
WHERE id = 2;

-- Step 5: Auto-populate connection_type for any other accounts
UPDATE connected_accounts
SET connection_type = CASE
    WHEN platform = 'instagram' AND access_token LIKE 'IGAAL%' THEN 'instagram_business_login'
    WHEN platform = 'instagram' AND access_token LIKE 'EAA%' THEN 'facebook_page'
    ELSE connection_type
END
WHERE platform = 'instagram' AND connection_type IS NULL;

-- Step 6: Verify the fixes
SELECT
    id,
    user_id,
    platform,
    connection_type,
    platform_user_id,
    page_id,
    platform_username,
    LEFT(access_token, 10) as token_prefix,
    CASE
        WHEN connection_type = 'instagram_business_login' THEN 'Uses graph.instagram.com'
        WHEN connection_type = 'facebook_page' THEN 'Uses graph.facebook.com/v18.0'
        ELSE 'Unknown'
    END as api_endpoint
FROM connected_accounts
WHERE platform = 'instagram'
ORDER BY id;

-- ========================================================================
-- EXPECTED RESULTS:
-- ========================================================================
-- Account 2 (livewithzaryab):
--   connection_type: facebook_page
--   platform_user_id: 17841470124898462 (Instagram Account ID)
--   page_id: 944710552063131 (Facebook Page ID)
--   api_endpoint: graph.facebook.com/v18.0
--
-- Account 5 (zaryab9299):
--   connection_type: instagram_business_login
--   platform_user_id: 17841479846631738 (Instagram Account ID for webhooks)
--   page_id: 25842486235386039 (Instagram-scoped User ID for API)
--   api_endpoint: graph.instagram.com
-- ========================================================================
