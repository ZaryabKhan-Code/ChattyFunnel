# Social Messaging Platform - Frontend

A Next.js 14 application for managing Facebook and Instagram messages with AI-powered automation.

## 📋 Prerequisites

- Node.js 18.x or higher
- npm or yarn

## 🚀 Getting Started

### 1. Install Dependencies

```bash
npm install
# or
yarn install
```

### 2. Environment Setup

Create a `.env.local` file in the frontend root directory:

```bash
cp .env.local.example .env.local
```

Edit `.env.local` with your configuration:

```env
NEXT_PUBLIC_API_URL=https://roamifly-admin-b97e90c67026.herokuapp.com/api
```

### 3. Run Development Server

```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Build for Production

```bash
npm run build
npm start
# or
yarn build
yarn start
```

## 📁 Project Structure

```
frontend/
├── app/                          # Next.js 14 App Router
│   ├── page.tsx                 # Login/Signup page
│   ├── workspace-setup/         # Workspace selection/creation
│   ├── dashboard/               # Main dashboard
│   │   ├── page.tsx            # Dashboard home with account status
│   │   ├── messages/           # Messages interface
│   │   └── bots/               # AI chatbot configuration
│   ├── funnels/                # Funnel management
│   ├── layout.tsx              # Root layout
│   └── globals.css             # Global styles
├── components/                  # Reusable React components
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── Input.tsx
│   ├── DashboardLayout.tsx
│   ├── LoadingSpinner.tsx
│   └── index.ts                # Component exports
├── hooks/                      # Custom React hooks
│   └── useWebSocket.ts         # WebSocket connection management
├── contexts/                   # React Context providers
│   └── WorkspaceContext.tsx    # Workspace state management
├── lib/                        # Utility functions and API clients
│   ├── api.ts                  # Main API client
│   └── api/                    # API modules
│       ├── workspaces.ts
│       ├── funnels.ts
│       └── ai-bots.ts
├── package.json                # Dependencies and scripts
├── tsconfig.json              # TypeScript configuration
├── next.config.js             # Next.js configuration
├── tailwind.config.js         # Tailwind CSS configuration
└── postcss.config.js          # PostCSS configuration
```

## 🎯 Features

### 1. **Authentication**
- Create new account with username
- Login with existing account ID
- Automatic session management with localStorage

### 2. **Workspace Management**
- Create multiple workspaces
- Switch between workspaces
- Each workspace has isolated data

### 3. **Social Account Integration**
- Connect Facebook Pages
- Connect Instagram Business accounts
- Visual connection status indicators
- Prevent duplicate accounts across workspaces

### 4. **Messaging**
- Real-time message updates via WebSocket
- Send and receive Facebook messages
- Send and receive Instagram messages
- Conversation list with participants
- Message history view

### 5. **Funnel Management**
- Create custom funnels
- Assign conversations to funnels
- Unassign conversations from funnels
- Visual kanban-style board
- Unassigned conversations column

### 6. **AI Chatbot**
- Create AI bots with custom configurations
- Support for OpenAI (GPT-4, GPT-3.5)
- Support for Anthropic (Claude 3 Opus, Sonnet)
- Custom system prompts
- Activate/deactivate bots

## 🔌 WebSocket Integration

The application uses WebSocket for real-time message updates:

```typescript
import { useWebSocket } from '@/hooks/useWebSocket'

const { isConnected, lastMessage, sendMessage } = useWebSocket(userId)
```

Features:
- Automatic reconnection with exponential backoff
- Heartbeat/ping-pong mechanism
- Message queuing for offline support
- Network status monitoring

## 🎨 Styling

- **Framework**: Tailwind CSS
- **Design**: Clean, minimal, functional
- **Color Scheme**: Gray, White, Blue
- **Responsive**: Mobile-first approach

## 📦 Dependencies

### Production
- `next`: 14.1.0 - React framework
- `react`: 18.2.0 - UI library
- `react-dom`: 18.2.0 - React DOM rendering
- `axios`: 1.6.5 - HTTP client
- `@headlessui/react`: 2.2.9 - Unstyled UI components
- `date-fns`: 3.6.0 - Date utilities

### Development
- `typescript`: ^5 - Type safety
- `tailwindcss`: ^3.3.0 - Utility-first CSS
- `autoprefixer`: ^10.0.1 - CSS vendor prefixing
- `postcss`: ^8 - CSS transformations

## 🛠️ Development

### Code Structure Guidelines

1. **Components**: Keep them simple and reusable
2. **Pages**: Use client-side rendering with `'use client'`
3. **API Calls**: Use axios for HTTP requests
4. **State Management**: Use React hooks and Context API
5. **Styling**: Use Tailwind utility classes

### API Integration

All API calls go through the configured API URL:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'
```

### Adding New Pages

1. Create a new directory under `app/`
2. Add `page.tsx` with your component
3. Use `DashboardLayout` for consistent navigation
4. Add route to navigation in `DashboardLayout.tsx`

## 🔐 Security

- No sensitive data stored in frontend
- API keys managed by backend
- User ID stored in localStorage (consider using secure cookies in production)
- Workspace ID stored in localStorage

## 🐛 Troubleshooting

### WebSocket not connecting
- Check if backend WebSocket endpoint is accessible
- Verify user ID is valid
- Check browser console for errors

### API calls failing
- Verify `NEXT_PUBLIC_API_URL` in `.env.local`
- Check backend server is running
- Verify CORS settings on backend

### Build errors
- Delete `.next` folder and rebuild
- Clear npm cache: `npm cache clean --force`
- Reinstall dependencies: `rm -rf node_modules && npm install`

## 📝 Notes

- This is a development setup. For production, add proper authentication
- Consider using NextAuth.js for production authentication
- Add error boundaries for better error handling
- Implement proper loading states
- Add unit and integration tests

## 🚀 Deployment

### Vercel (Recommended for Next.js)

```bash
npm install -g vercel
vercel
```

### Other Platforms

Build the application:
```bash
npm run build
```

Start the production server:
```bash
npm start
```

## 📄 License

Private project - All rights reserved
