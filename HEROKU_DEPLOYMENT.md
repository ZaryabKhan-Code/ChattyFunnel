# Deploying to Heroku - Complete Guide

This guide will walk you through deploying the FastAPI backend to Heroku.

## Prerequisites

1. **Heroku Account**: Sign up at [heroku.com](https://heroku.com)
2. **Heroku CLI**: Install from [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)
3. **Git**: Ensure Git is installed
4. **Facebook App**: Have your Facebook App credentials ready

## Step 1: Install Heroku CLI

```bash
# macOS
brew tap heroku/brew && brew install heroku

# Windows
# Download installer from https://devcenter.heroku.com/articles/heroku-cli

# Ubuntu/Debian
curl https://cli-assets.heroku.com/install.sh | sh
```

## Step 2: Login to Heroku

```bash
heroku login
```

This will open a browser for authentication.

## Step 3: Create a Heroku App

```bash
# Navigate to backend directory
cd backend

# Create Heroku app (replace 'your-app-name' with your desired name)
heroku create your-app-name

# Or let Heroku generate a name
heroku create
```

Note your app URL: `https://your-app-name.herokuapp.com`

## Step 4: Add PostgreSQL Database

Heroku doesn't support SQLite (ephemeral filesystem). We'll use PostgreSQL:

```bash
# Add Heroku Postgres (free tier)
heroku addons:create heroku-postgresql:mini

# Check database info
heroku pg:info
```

Heroku will automatically set the `DATABASE_URL` environment variable.

## Step 5: Set Environment Variables

Set all required environment variables on Heroku:

```bash
# Facebook App Settings
heroku config:set FACEBOOK_APP_ID=your_facebook_app_id
heroku config:set FACEBOOK_APP_SECRET=your_facebook_app_secret
heroku config:set FACEBOOK_REDIRECT_URI=https://your-app-name.herokuapp.com/api/auth/facebook/callback

# Instagram App Settings (usually same as Facebook)
heroku config:set INSTAGRAM_APP_ID=your_facebook_app_id
heroku config:set INSTAGRAM_APP_SECRET=your_facebook_app_secret
heroku config:set INSTAGRAM_REDIRECT_URI=https://your-app-name.herokuapp.com/api/auth/instagram/callback

# Application Settings
heroku config:set SECRET_KEY=$(openssl rand -hex 32)
heroku config:set FRONTEND_URL=https://your-frontend-url.vercel.app
heroku config:set ENVIRONMENT=production
heroku config:set API_V1_STR=/api

# Verify all config vars
heroku config
```

## Step 6: Update Facebook App Settings

In your Facebook App Dashboard:

1. Go to **Settings** > **Basic**
   - Add **App Domains**: `your-app-name.herokuapp.com`

2. Go to **Facebook Login** > **Settings**
   - Add **Valid OAuth Redirect URIs**:
     - `https://your-app-name.herokuapp.com/api/auth/facebook/callback`
     - `https://your-app-name.herokuapp.com/api/auth/instagram/callback`

3. Go to **Webhooks** > **Page**
   - Edit Callback URL: `https://your-app-name.herokuapp.com/api/webhooks/facebook`
   - Edit Verify Token: (set same token in your code)

## Step 7: Deploy to Heroku

### Option A: Deploy from Local Git

```bash
# Make sure you're in the backend directory
cd backend

# Initialize git if not already done
git init
git add .
git commit -m "Prepare for Heroku deployment"

# Add Heroku remote
heroku git:remote -a your-app-name

# Deploy
git push heroku main

# Or if your branch is named differently
git push heroku your-branch-name:main
```

### Option B: Deploy from GitHub

1. Connect your GitHub repository to Heroku:
   ```bash
   # Go to Heroku Dashboard
   # Select your app > Deploy tab
   # Choose GitHub as deployment method
   # Connect your repository
   # Enable automatic deploys (optional)
   ```

2. Trigger manual deploy from main branch

## Step 8: Initialize Database

After deployment, run database migrations:

```bash
# Open Heroku Python console
heroku run python

# In the Python console:
>>> from app.database import init_db
>>> init_db()
>>> exit()
```

Or create a one-off dyno:

```bash
heroku run python -c "from app.database import init_db; init_db()"
```

## Step 9: Verify Deployment

```bash
# Open your app in browser
heroku open

# Check logs
heroku logs --tail

# Check API health
curl https://your-app-name.herokuapp.com/health

# Check API docs
# Visit: https://your-app-name.herokuapp.com/docs
```

## Step 10: Scale Dynos (if needed)

```bash
# Check current dyno status
heroku ps

# Scale web dyno
heroku ps:scale web=1

# For production, you might want more:
# heroku ps:scale web=2
```

## Troubleshooting

### Check Logs

```bash
# View live logs
heroku logs --tail

# View recent logs
heroku logs --tail --num 500

# View specific process logs
heroku logs --tail --ps web
```

### Database Issues

```bash
# Check database connection
heroku pg:psql

# Reset database (WARNING: deletes all data)
heroku pg:reset DATABASE_URL
heroku run python -c "from app.database import init_db; init_db()"
```

### Application Crashes

```bash
# Restart all dynos
heroku restart

# Restart specific dyno
heroku restart web.1
```

### Check Environment Variables

```bash
# List all config vars
heroku config

# Get specific var
heroku config:get DATABASE_URL

# Remove var
heroku config:unset VARIABLE_NAME
```

## Updating Your App

```bash
# Make changes to your code
git add .
git commit -m "Your commit message"

# Push to Heroku
git push heroku main

# Check deployment
heroku logs --tail
```

## Cost Optimization

### Free Tier Limitations:
- **Dynos**: 550-1000 free dyno hours/month
- **Postgres**: 10,000 rows (Mini plan is paid but cheap)
- **App sleeps**: After 30 minutes of inactivity

### Tips:
1. Use **Heroku Scheduler** instead of always-on workers
2. Enable **automatic SSL** (free with Heroku)
3. Monitor usage in Heroku Dashboard

## Security Best Practices

1. **Never commit** `.env` files
2. **Use strong** `SECRET_KEY` (generated with openssl)
3. **Enable HTTPS** only in Facebook App settings
4. **Rotate secrets** regularly
5. **Monitor logs** for suspicious activity

## Custom Domain (Optional)

```bash
# Add custom domain
heroku domains:add www.yourdomain.com

# Get DNS target
heroku domains

# Update your DNS records to point to Heroku
```

## CI/CD with GitHub Actions (Optional)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Heroku

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: akhileshns/heroku-deploy@v3.12.12
        with:
          heroku_api_key: ${{secrets.HEROKU_API_KEY}}
          heroku_app_name: "your-app-name"
          heroku_email: "your-email@example.com"
          appdir: "backend"
```

## Monitoring

```bash
# View app metrics
heroku logs --tail

# Add monitoring (paid add-on)
heroku addons:create papertrail

# Check app status
heroku apps:info
```

## Rollback (if needed)

```bash
# View releases
heroku releases

# Rollback to previous release
heroku rollback

# Rollback to specific version
heroku rollback v123
```

## Support Resources

- [Heroku Dev Center](https://devcenter.heroku.com/)
- [Heroku Python Support](https://devcenter.heroku.com/articles/python-support)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/docker/)
- [PostgreSQL on Heroku](https://devcenter.heroku.com/articles/heroku-postgresql)

## Next Steps

After deploying backend:
1. Deploy frontend to Vercel/Netlify
2. Update `FRONTEND_URL` in Heroku config
3. Update `NEXT_PUBLIC_API_URL` in frontend
4. Test OAuth flows end-to-end
5. Set up monitoring and alerts
