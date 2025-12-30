-- This SQL fixes Instagram Business Login account IDs
-- Run this ONCE on Heroku: 
-- heroku pg:psql --app roamifly-admin-b97e90c67026 < FIX_INSTAGRAM_ACCOUNT.sql

-- Show current state
SELECT id, user_id, platform_user_id, page_id, platform_username 
FROM connected_accounts 
WHERE platform = 'instagram' AND access_token LIKE 'IGAAL%';

-- Fix account 5: Update platform_user_id to Instagram Account ID
-- This ID comes from /me endpoint and is used in webhooks
UPDATE connected_accounts 
SET platform_user_id = '17841479846631738'
WHERE id = 5;

-- Verify the fix
SELECT id, user_id, platform_user_id, page_id, platform_username 
FROM connected_accounts 
WHERE id = 5;
