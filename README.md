# Social Messaging Integration App

A full-stack application that allows users to connect their Facebook and Instagram accounts to send and receive messages through a unified interface, similar to CRM social messaging features.

## Features

- **OAuth Integration**: Secure connection with Facebook and Instagram accounts
- **Unified Messaging**: Send and receive messages from both platforms in one interface
- **Real-time Webhooks**: Receive incoming messages automatically
- **Multi-Account Support**: Connect multiple Facebook pages and Instagram accounts
- **Message History**: View and sync conversation history
- **Modern UI**: Clean, responsive interface built with Next.js and Tailwind CSS

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLite/PostgreSQL**: SQLite for local development, PostgreSQL for production (Heroku)
- **SQLAlchemy**: ORM for database operations
- **Facebook Graph API**: Integration with Facebook and Instagram

### Frontend
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe JavaScript
- **Tailwind CSS**: Utility-first CSS framework
- **Axios**: HTTP client for API requests

## Prerequisites

Before you begin, ensure you have:

1. **Python 3.8+** installed
2. **Node.js 18+** and npm installed
3. **Facebook App** created with the following:
   - App ID and App Secret
   - Instagram Business account linked (for Instagram messaging)
   - Required permissions configured

## Facebook App Setup

### 1. Create a Facebook App

1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Click "My Apps" > "Create App"
3. Select "Business" as the app type
4. Fill in the app details and create

### 2. Configure App Settings

1. In your app dashboard, go to **Settings** > **Basic**
2. Add your **App Domains**: `localhost`
3. Note your **App ID** and **App Secret**

### 3. Add Products

Add the following products to your app:
- **Facebook Login**
- **Webhooks**

### 4. Configure Facebook Login

1. Go to **Facebook Login** > **Settings**
2. Add OAuth Redirect URIs:
   - `http://localhost:8000/api/auth/facebook/callback`
   - `http://localhost:8000/api/auth/instagram/callback`

### 5. Configure Webhooks

1. Go to **Webhooks** in your app dashboard
2. Click "Edit Subscription" for **Page**
3. Add Callback URL: `http://localhost:8000/api/webhooks/facebook`
4. Add Verify Token: `your_verify_token_here` (you'll need to update this in the code)
5. Subscribe to fields:
   - `messages`
   - `messaging_postbacks`

### 6. Required Permissions

Your app needs these permissions:
- `pages_messaging` - Send/receive messages
- `pages_manage_metadata` - Manage page metadata
- `pages_read_engagement` - Read page engagement
- `pages_show_list` - List pages
- `instagram_basic` - Basic Instagram profile
- `instagram_manage_messages` - Instagram messaging

### 7. Instagram Business Account

For Instagram messaging:
1. Convert your Instagram account to a Business account
2. Connect it to a Facebook Page
3. The Facebook Page will be used to authenticate Instagram messaging

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd facebook-Insta
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env
```

### 3. Configure Backend Environment

Edit `backend/.env` with your credentials:

```env
# Facebook App Credentials
FACEBOOK_APP_ID=your_facebook_app_id_here
FACEBOOK_APP_SECRET=your_facebook_app_secret_here
FACEBOOK_REDIRECT_URI=http://localhost:8000/api/auth/facebook/callback

# Instagram App Credentials (same as Facebook)
INSTAGRAM_APP_ID=your_facebook_app_id_here
INSTAGRAM_APP_SECRET=your_facebook_app_secret_here
INSTAGRAM_REDIRECT_URI=http://localhost:8000/api/auth/instagram/callback

# Application Settings
SECRET_KEY=your-secret-key-change-this-in-production
DATABASE_URL=sqlite:///./social_messaging.db
FRONTEND_URL=http://localhost:3000

# API Settings
API_V1_STR=/api
```

### 4. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Create .env.local file
cp .env.local.example .env.local
```

Edit `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## Running the Application

### 1. Start the Backend

```bash
cd backend

# Make sure virtual environment is activated
# Run the FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

### 2. Start the Frontend

In a new terminal:

```bash
cd frontend

# Run the Next.js development server
npm run dev
```

The frontend will be available at: http://localhost:3000

## Usage Guide

### 1. Create an Account

1. Open http://localhost:3000
2. Enter a username (and optionally an email)
3. Click "Create Account"
4. You'll be redirected to the dashboard

### 2. Connect Facebook

1. On the dashboard, click "Connect Facebook"
2. You'll be redirected to Facebook login
3. Grant the required permissions
4. Select the Facebook Pages you want to manage
5. You'll be redirected back to the dashboard

### 3. Connect Instagram

1. On the dashboard, click "Connect Instagram"
2. Grant the required permissions
3. Your Instagram Business accounts will be automatically linked
4. You'll be redirected back to the dashboard

### 4. Send and Receive Messages

1. Click "Go to Messages" on the dashboard
2. Select an account from the dropdown
3. Click "Sync" to load conversations
4. Select a conversation to view messages
5. Type a message and click "Send"

## API Endpoints

### Users
- `POST /api/users/` - Create a new user
- `GET /api/users/{user_id}` - Get user details
- `GET /api/users/` - List all users

### Authentication
- `GET /api/auth/facebook/login` - Initiate Facebook OAuth
- `GET /api/auth/facebook/callback` - Facebook OAuth callback
- `GET /api/auth/instagram/login` - Initiate Instagram OAuth
- `GET /api/auth/instagram/callback` - Instagram OAuth callback

### Accounts
- `GET /api/accounts/{user_id}` - Get connected accounts
- `DELETE /api/accounts/{account_id}` - Disconnect account
- `POST /api/accounts/{account_id}/reactivate` - Reactivate account

### Messages
- `POST /api/messages/send` - Send a message
- `GET /api/messages/conversations` - Get conversations
- `GET /api/messages/conversation/{conversation_id}` - Get messages
- `GET /api/messages/sync` - Sync messages from platform

### Webhooks
- `GET /api/webhooks/facebook` - Verify Facebook webhook
- `POST /api/webhooks/facebook` - Receive Facebook messages
- `GET /api/webhooks/instagram` - Verify Instagram webhook
- `POST /api/webhooks/instagram` - Receive Instagram messages

## Deployment

### Deploy Backend to Heroku

The backend is ready for Heroku deployment with PostgreSQL database.

#### Quick Deploy (Automated Script)

```bash
cd backend
chmod +x deploy.sh
./deploy.sh
```

The script will guide you through:
- Creating/selecting Heroku app
- Adding PostgreSQL database
- Setting environment variables
- Deploying the application
- Initializing the database

#### Manual Deploy

For detailed step-by-step instructions, see **[HEROKU_DEPLOYMENT.md](HEROKU_DEPLOYMENT.md)**

**Quick commands:**
```bash
# Login to Heroku
heroku login

# Create app
heroku create your-app-name

# Add PostgreSQL
heroku addons:create heroku-postgresql:mini

# Set environment variables
heroku config:set FACEBOOK_APP_ID=your_app_id
heroku config:set FACEBOOK_APP_SECRET=your_secret
# ... (see HEROKU_DEPLOYMENT.md for all variables)

# Deploy
git push heroku main

# Initialize database
heroku run python -c "from app.database import init_db; init_db()"
```

**Important**: After deploying to Heroku, update your Facebook App settings with the new URLs:
- **OAuth Redirect URIs**: `https://your-app.herokuapp.com/api/auth/facebook/callback`
- **Webhook URL**: `https://your-app.herokuapp.com/api/webhooks/facebook`

### Deploy Frontend

Deploy the Next.js frontend to Vercel or Netlify:

**Vercel (Recommended):**
```bash
cd frontend
npm install -g vercel
vercel --prod
```

**Netlify:**
```bash
cd frontend
npm run build
netlify deploy --prod --dir=.next
```

Update environment variable:
- `NEXT_PUBLIC_API_URL`: Your Heroku backend URL

## Webhook Configuration for Production

For production use with real webhooks:

1. **Deploy your backend** to Heroku (see Deployment section above)
2. **Update webhook URLs** in Facebook App settings to your Heroku domain
3. **Update the verify token** in `backend/app/routers/webhooks.py`:
   ```python
   VERIFY_TOKEN = "your_secure_verify_token_here"
   ```
4. **Use HTTPS** - Facebook requires HTTPS for webhooks (Heroku provides this automatically)
5. **Update environment variables** with production URLs

## Database Schema

The application uses SQLite for local development and PostgreSQL for production (Heroku).

**Tables:**
- **users**: User accounts
- **connected_accounts**: Linked social media accounts
- **messages**: Message history

**Note**: The application automatically handles both SQLite and PostgreSQL connections. When deploying to Heroku, PostgreSQL is configured automatically.

## Security Considerations

1. **Never commit** your `.env` files
2. **Use strong secrets** in production
3. **Enable HTTPS** for production
4. **Validate webhook signatures** (already implemented)
5. **Store tokens securely** (currently in database - consider encryption for production)
6. **Implement rate limiting** for production
7. **Add authentication** for API endpoints in production

## Troubleshooting

### Backend Issues

**Database errors:**
```bash
# Delete the database and restart
rm backend/social_messaging.db
# Restart the backend - database will be recreated
```

**Import errors:**
```bash
# Make sure you're in the backend directory
cd backend
# Reinstall dependencies
pip install -r requirements.txt
```

### Frontend Issues

**Module not found:**
```bash
# Delete node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

**API connection errors:**
- Check that backend is running on port 8000
- Verify `NEXT_PUBLIC_API_URL` in `.env.local`

### OAuth Issues

**Redirect URI mismatch:**
- Ensure redirect URIs in Facebook App match exactly with your `.env` settings
- URIs are case-sensitive

**Permission errors:**
- Verify all required permissions are added in Facebook App settings
- For Instagram, ensure account is a Business account

## Development

### Project Structure

```
facebook-Insta/
├── backend/
│   ├── app/
│   │   ├── models/          # Database models
│   │   ├── routers/         # API endpoints
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── config.py        # Configuration
│   │   ├── database.py      # Database setup
│   │   └── main.py          # FastAPI app
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/                 # Next.js pages
│   ├── components/          # React components
│   ├── lib/                 # Utilities
│   ├── package.json
│   └── .env.local.example
└── README.md
```

## Future Enhancements

- [ ] Real-time message updates using WebSockets
- [ ] User authentication and sessions
- [ ] Message attachments (images, videos)
- [ ] Message reactions and read receipts
- [ ] Advanced search and filtering
- [ ] Analytics and reporting
- [ ] Multi-language support
- [ ] Dark mode
- [ ] Mobile app

## License

MIT

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Facebook API documentation
3. Open an issue on GitHub

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
