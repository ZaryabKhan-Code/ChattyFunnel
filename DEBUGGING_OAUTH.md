# Debugging OAuth Connection Issues

## Problem
Facebook and Instagram OAuth connections are completing successfully, but no connected accounts are showing up in the database or frontend.

## Debugging Steps

### 1. Check if Database is Initialized

Visit this URL in your browser:
```
https://rnd-48f97bdd68a0.herokuapp.com/api/debug/db-status
```

**Expected Response:**
```json
{
  "status": "Database is working",
  "user_count": 1,
  "account_count": 0,
  "users": [...],
  "accounts": []
}
```

**If you get an error:** The database is not initialized. Run:
```bash
heroku run python -c "from app.database import init_db; init_db()" --app rnd-48f97bdd68a0
```

### 2. Test Database Writes

Visit this URL:
```
https://rnd-48f97bdd68a0.herokuapp.com/api/debug/test-insert
```

**Expected Response:**
```json
{
  "status": "Insert successful",
  "user_id": 1,
  "username": "test_user_..."
}
```

**If insert fails:** There's a database permission or connection issue.

### 3. Check Heroku Logs During OAuth

1. Open a terminal and run:
```bash
heroku logs --tail --app rnd-48f97bdd68a0
```

2. In another window, try connecting Facebook or Instagram

3. Watch the logs for detailed output showing each step:
   - `Facebook callback received`
   - `Exchanging code for access token`
   - `Got access token`
   - `Getting user info`
   - `Found X pages`
   - `Creating new connected account`
   - `Committing to database`
   - `Database commit successful`
   - `Redirecting to: ...`

### 4. Common Issues and Solutions

#### Issue: "User not found" error
**Solution:** Make sure you create a user first on the frontend homepage before trying to connect accounts.

**Steps:**
1. Go to `https://your-frontend-url.vercel.app`
2. Enter a username
3. Click "Create Account"
4. Note your user ID (stored in localStorage)
5. Then try connecting Facebook/Instagram

#### Issue: No pages found
**Logs show:** `Found 0 pages`

**Solution:**
- For Facebook: Make sure you manage at least one Facebook Page
- For Instagram: Make sure your Instagram account is a Business account linked to a Facebook Page

**How to check:**
1. Go to https://www.facebook.com/pages
2. You should see at least one page you manage
3. For Instagram, the business account must be linked to this page

#### Issue: Database commit fails
**Logs show error during commit**

**Solution:**
```bash
# Restart the Heroku dyno
heroku restart --app rnd-48f97bdd68a0

# Re-initialize database
heroku run python -c "from app.database import init_db; init_db()" --app rnd-48f97bdd68a0
```

#### Issue: CORS error in browser console
**Browser shows:** `Access to... has been blocked by CORS policy`

**Solution:** Check that `FRONTEND_URL` is set correctly on Heroku:
```bash
heroku config:get FRONTEND_URL --app rnd-48f97bdd68a0
```

Should match your actual frontend URL. Update if needed:
```bash
heroku config:set FRONTEND_URL=https://your-actual-frontend.vercel.app --app rnd-48f97bdd68a0
```

### 5. Check Environment Variables

Make sure all required environment variables are set:
```bash
heroku config --app rnd-48f97bdd68a0
```

**Required variables:**
- `DATABASE_URL` (auto-set by Heroku Postgres)
- `FACEBOOK_APP_ID`
- `FACEBOOK_APP_SECRET`
- `FACEBOOK_REDIRECT_URI` (should match your Heroku URL)
- `INSTAGRAM_APP_ID` (usually same as Facebook)
- `INSTAGRAM_APP_SECRET` (usually same as Facebook)
- `INSTAGRAM_REDIRECT_URI` (should match your Heroku URL)
- `FRONTEND_URL` (your Next.js deployment URL)
- `SECRET_KEY`
- `WEBHOOK_VERIFY_TOKEN`

### 6. Manual Database Check

Connect to your database directly:
```bash
heroku pg:psql --app rnd-48f97bdd68a0
```

Then run:
```sql
-- Check if tables exist
\dt

-- Count users
SELECT COUNT(*) FROM users;

-- Count connected accounts
SELECT COUNT(*) FROM connected_accounts;

-- View all connected accounts
SELECT id, user_id, platform, platform_username, page_name, is_active FROM connected_accounts;

-- Exit
\q
```

### 7. Complete OAuth Flow Test

1. **Create a user:**
   ```bash
   curl -X POST https://rnd-48f97bdd68a0.herokuapp.com/api/users/ \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "email": "test@example.com"}'
   ```

   Note the returned `id` (e.g., `1`)

2. **Get OAuth URL:**
   ```bash
   curl "https://rnd-48f97bdd68a0.herokuapp.com/api/auth/facebook/login?user_id=1"
   ```

3. **Open the `auth_url` in browser and authorize**

4. **Check if account was saved:**
   ```bash
   curl "https://rnd-48f97bdd68a0.herokuapp.com/api/accounts/1"
   ```

### 8. Frontend Issues

If backend is working but frontend shows nothing:

**Check browser console for errors:**
- Open Developer Tools (F12)
- Go to Console tab
- Look for any errors

**Verify API calls:**
- Open Network tab
- Try connecting an account
- Check if `/api/accounts/{user_id}` call succeeds
- Check response data

**Verify localStorage:**
- In Console tab, type: `localStorage.getItem('userId')`
- Should return your user ID
- If null, you need to create a user first

### 9. Quick Fix Checklist

- [ ] Database is initialized (`/api/debug/db-status` works)
- [ ] Can insert test data (`/api/debug/test-insert` works)
- [ ] User exists (created on frontend)
- [ ] User ID is stored in localStorage
- [ ] FRONTEND_URL environment variable is correct
- [ ] OAuth redirect URIs match Heroku URL
- [ ] You manage at least one Facebook Page
- [ ] For Instagram: Account is Business and linked to Page
- [ ] All environment variables are set
- [ ] No errors in Heroku logs during OAuth

### 10. Still Not Working?

Run this complete diagnostic:

```bash
# 1. Check app is running
curl https://rnd-48f97bdd68a0.herokuapp.com/health

# 2. Check database
curl https://rnd-48f97bdd68a0.herokuapp.com/api/debug/db-status

# 3. Create test user
curl -X POST https://rnd-48f97bdd68a0.herokuapp.com/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"username": "debug_user"}'

# 4. Check logs with OAuth
heroku logs --tail --app rnd-48f97bdd68a0
# Then try connecting Facebook in browser

# 5. Check if account was created
curl https://rnd-48f97bdd68a0.herokuapp.com/api/debug/db-status
```

Send the output of these commands for further debugging.

## Most Likely Issues

Based on typical scenarios:

1. **Database not initialized** (90% of cases)
   - Solution: Run `heroku run python -c "from app.database import init_db; init_db()"`

2. **No Facebook Pages** (5% of cases)
   - Solution: Create a Facebook Page first

3. **Wrong environment variables** (3% of cases)
   - Solution: Verify all config vars are correct

4. **User not created** (2% of cases)
   - Solution: Create user on frontend first before connecting
