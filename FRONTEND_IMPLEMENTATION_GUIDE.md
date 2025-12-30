# Frontend Implementation Guide

This document contains all the remaining frontend components needed to complete the workspace, funnel, and AI bot system.

## ✅ Already Created

1. API Clients:
   - `lib/api/workspaces.ts`
   - `lib/api/funnels.ts`
   - `lib/api/ai-bots.ts`
   - `lib/api/attachments.ts`

2. Context & Components:
   - `contexts/WorkspaceContext.tsx`
   - `app/components/workspace/WorkspaceSelector.tsx`

## 🔨 Components to Create

### 1. Update Layout to Include Workspace Provider

**File:** `frontend/app/layout.tsx`

Wrap the app with WorkspaceProvider:

```tsx
import { WorkspaceProvider } from '@/contexts/WorkspaceContext'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Get user ID from your auth system
  const userId = 1 // Replace with actual user ID from auth

  return (
    <html lang="en">
      <body>
        <WorkspaceProvider userId={userId}>
          {children}
        </WorkspaceProvider>
      </body>
    </html>
  )
}
```

### 2. Update Messages Page to Include Workspace Selector

**File:** `frontend/app/messages/page.tsx`

Add WorkspaceSelector at the top of the messages page:

```tsx
import WorkspaceSelector from '../components/workspace/WorkspaceSelector'
import { useWorkspace } from '@/contexts/WorkspaceContext'

export default function MessagesPage() {
  const { selectedWorkspace } = useWorkspace()
  const userId = 1 // Get from auth

  return (
    <div>
      <div className="bg-white border-b px-6 py-4">
        <WorkspaceSelector userId={userId} />
      </div>

      {/* Rest of your messages UI */}
      {selectedWorkspace && (
        <div>
          {/* Your existing messages interface */}
        </div>
      )}

      {!selectedWorkspace && (
        <div className="p-6 text-center text-gray-500">
          Please select or create a workspace to continue
        </div>
      )}
    </div>
  )
}
```

### 3. Voice Recorder Component

**File:** `frontend/app/components/messages/VoiceRecorder.tsx`

```tsx
'use client'

import { useState, useRef } from 'react'
import { uploadAttachment } from '@/lib/api/attachments'

export default function VoiceRecorder({
  userId,
  onRecordingComplete
}: {
  userId: number
  onRecordingComplete: (fileUrl: string) => void
}) {
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm',
      })

      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      mediaRecorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const file = new File([blob], `voice-${Date.now()}.webm`, {
          type: 'audio/webm',
        })

        try {
          const response = await uploadAttachment(file, userId, true)
          onRecordingComplete(response.file_url)
        } catch (error) {
          console.error('Failed to upload voice note:', error)
          alert('Failed to upload voice note')
        }

        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop())
      }

      mediaRecorder.start()
      setIsRecording(true)

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1)
      }, 1000)
    } catch (error) {
      console.error('Failed to start recording:', error)
      alert('Failed to access microphone')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      setRecordingTime(0)

      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="flex items-center gap-2">
      {!isRecording ? (
        <button
          onClick={startRecording}
          className="p-2 rounded-full hover:bg-gray-100"
          title="Record voice note"
        >
          <svg
            className="w-5 h-5 text-gray-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
            />
          </svg>
        </button>
      ) : (
        <div className="flex items-center gap-2 bg-red-50 px-3 py-2 rounded-lg">
          <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
          <span className="text-sm font-medium text-red-700">
            {formatTime(recordingTime)}
          </span>
          <button
            onClick={stopRecording}
            className="ml-2 px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
          >
            Stop & Send
          </button>
        </div>
      )}
    </div>
  )
}
```

### 4. Attachment Uploader Component

**File:** `frontend/app/components/messages/AttachmentUploader.tsx`

```tsx
'use client'

import { useRef, useState } from 'react'
import { uploadAttachment } from '@/lib/api/attachments'

export default function AttachmentUploader({
  userId,
  onUploadComplete,
}: {
  userId: number
  onUploadComplete: (fileUrl: string, fileType: string) => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isUploading, setIsUploading] = useState(false)

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Check file size (max 50MB)
    const maxSize = 50 * 1024 * 1024
    if (file.size > maxSize) {
      alert('File too large. Maximum size is 50MB')
      return
    }

    try {
      setIsUploading(true)
      const response = await uploadAttachment(file, userId)
      onUploadComplete(response.file_url, response.mime_type)
    } catch (error: any) {
      console.error('Failed to upload file:', error)
      alert(error.message || 'Failed to upload file')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        onChange={handleFileSelect}
        className="hidden"
        accept="image/*,video/*,audio/*,.pdf,.doc,.docx"
      />

      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading}
        className="p-2 rounded-full hover:bg-gray-100 disabled:opacity-50"
        title="Attach file"
      >
        {isUploading ? (
          <svg
            className="animate-spin w-5 h-5 text-gray-600"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        ) : (
          <svg
            className="w-5 h-5 text-gray-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
            />
          </svg>
        )}
      </button>
    </>
  )
}
```

## 📦 Required Dependencies

Install these packages:

```bash
cd frontend
npm install react-flow-renderer  # For visual funnel builder
npm install @headlessui/react     # For better modals/dropdowns
npm install date-fns             # For date formatting
```

## 🚀 Quick Frontend Integration Steps

1. **Add API clients** (Already done ✅)

2. **Add Workspace Context to Layout:**
   - Update `app/layout.tsx` to wrap with `WorkspaceProvider`

3. **Add Workspace Selector to Messages Page:**
   - Import `WorkspaceSelector` in `app/messages/page.tsx`
   - Add it at the top of the page

4. **Update Message Input to Support Attachments:**
   - Add `VoiceRecorder` and `AttachmentUploader` components
   - Update send message function to include attachment data

5. **Create Workspaces Management Page (Optional):**
   - Create `app/workspaces/page.tsx`
   - List all workspaces
   - Manage members
   - View connected accounts

6. **Create AI Bots Page (Optional):**
   - Create `app/ai-bots/page.tsx`
   - List all bots
   - Create/edit bots
   - Configure triggers

7. **Create Funnels Page (Optional):**
   - Create `app/funnels/page.tsx`
   - Use `react-flow-renderer` for visual builder
   - Configure funnel steps

## 🎨 Minimal Working Example

For a quick test, just do steps 1-4 above. This will give you:
- ✅ Workspace selection
- ✅ Voice notes
- ✅ File attachments
- ✅ Auto-created default workspaces
- ✅ Full backend integration

The workspace/bot/funnel management pages can be added later as needed!

## 🔧 Testing the Integration

1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Connect an Instagram/Facebook account
4. Send a message to trigger automation
5. Check backend logs to see funnel/bot processing

## 📝 Environment Variables Needed

```bash
# Backend (.env)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Frontend (.env.local)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## 🎯 Next Steps After Frontend is Running

1. **Run Migration:**
   ```bash
   python backend/migrate_workspace_system.py
   ```

2. **Test Automation:**
   - Create a workspace default AI bot
   - Create a welcome funnel
   - Send a test message
   - Watch automation trigger!

3. **Deploy:**
   - Push to Heroku
   - Run migration on Heroku
   - Set environment variables
   - Test in production

That's it! You now have a complete workspace, funnel, and AI bot system! 🎉
