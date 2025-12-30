'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import DashboardLayout from '@/components/DashboardLayout'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

// Proxy profile pictures through backend to avoid CDN expiration issues
const getProxiedProfilePic = (url: string | undefined): string | undefined => {
  if (!url) return undefined
  // Only proxy Instagram/Facebook CDN URLs that tend to expire
  if (url.includes('cdninstagram.com') || url.includes('fbcdn.net') || url.includes('scontent')) {
    return `${API_URL}/media/profile-pic?url=${encodeURIComponent(url)}`
  }
  return url
}

// Proxy media attachments (images, videos, audio) through backend
const getProxiedMediaUrl = (url: string | undefined): string | undefined => {
  if (!url) return undefined
  // Proxy Instagram/Facebook CDN URLs that tend to expire
  if (url.includes('cdninstagram.com') || url.includes('fbcdn.net') || url.includes('scontent')) {
    return `${API_URL}/media/profile-pic?url=${encodeURIComponent(url)}`
  }
  return url
}

interface Conversation {
  id: string
  participant_name: string
  participant_username: string
  participant_profile_pic?: string
  last_message?: string
  updated_at?: string
  platform?: string
}

interface Message {
  id: number
  message_text: string
  content?: string
  direction: string
  created_at: string
  sender_id: string
  message_type?: string
  attachment_url?: string
  attachment_type?: string
  attachment_filename?: string
}

interface AttachmentPreview {
  file: File
  url: string
  type: 'image' | 'video' | 'audio' | 'file'
}

export default function Messages() {
  const [userId, setUserId] = useState<number | null>(null)
  const [workspaceId, setWorkspaceId] = useState<number | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [messageInput, setMessageInput] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Attachment state
  const [attachment, setAttachment] = useState<AttachmentPreview | null>(null)
  const [uploadingAttachment, setUploadingAttachment] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // WebSocket context - connection is managed globally
  const { isConnected, lastMessage, sendMessage: wsSendMessage } = useWebSocketContext()

  useEffect(() => {
    const storedUserId = localStorage.getItem('userId')
    const storedWorkspaceId = localStorage.getItem('workspaceId')

    if (!storedUserId || !storedWorkspaceId) {
      router.push('/')
      return
    }

    setUserId(parseInt(storedUserId))
    setWorkspaceId(parseInt(storedWorkspaceId))
    loadConversations(parseInt(storedWorkspaceId))
  }, [router])

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage && lastMessage.type === 'new_message') {
      console.log('New message received via WebSocket:', lastMessage.data)
      const newMsg = lastMessage.data.message
      const convId = lastMessage.data.conversation_id

      // If we're viewing the conversation that received the message, add it immediately
      if (selectedConversation === convId && newMsg) {
        setMessages(prev => {
          // Check if message already exists to avoid duplicates
          const exists = prev.some(m => m.id === newMsg.id)
          if (exists) return prev

          // Add the new message
          const newMessage: Message = {
            id: newMsg.id,
            message_text: newMsg.content || '',
            content: newMsg.content || '',
            direction: newMsg.direction || 'incoming',
            created_at: newMsg.created_at,
            sender_id: newMsg.sender_id,
            message_type: newMsg.message_type,
            attachment_url: newMsg.attachment_url,
            attachment_type: newMsg.attachment_type
          }
          return [...prev, newMessage]
        })
      }

      // Update conversations list to show new last message
      if (workspaceId) {
        loadConversations(workspaceId)
      }
    }
  }, [lastMessage, workspaceId, selectedConversation])

  // Polling fallback - check for new messages every 5 seconds as backup
  // This catches messages missed during WebSocket reconnection or deploy
  useEffect(() => {
    if (!selectedConversation) return

    const pollInterval = setInterval(() => {
      // Only poll if WebSocket is not connected
      if (!isConnected) {
        console.log('📡 Polling for new messages (WebSocket disconnected)')
        loadMessages(selectedConversation)
      }
    }, 5000)

    return () => clearInterval(pollInterval)
  }, [selectedConversation, isConnected])

  const loadConversations = async (wid: number) => {
    try {
      console.log('Loading conversations for workspace:', wid)
      const response = await axios.get(`${API_URL}/messages/conversations?workspace_id=${wid}`)
      console.log('Loaded conversations:', response.data)

      // Deduplicate conversations by ID to prevent duplicate key warnings
      const uniqueConversations = Array.from(
        new Map(response.data.map((c: Conversation) => [c.id, c])).values()
      )
      setConversations(uniqueConversations)

      if (response.data.length === 0) {
        console.warn('No conversations found for workspace', wid)
      }
    } catch (error: any) {
      console.error('Failed to load conversations:', error)
      console.error('Error details:', error.response?.data)
    }
  }

  const loadMessages = async (conversationId: string) => {
    try {
      setLoading(true)
      const response = await axios.get(`${API_URL}/messages/conversations/${conversationId}/messages`)

      // Deduplicate messages by ID to prevent duplicate key warnings
      const uniqueMessages = Array.from(
        new Map(response.data.map((m: Message) => [m.id, m])).values()
      )
      setMessages(uniqueMessages)
    } catch (error) {
      console.error('Failed to load messages:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectConversation = (conversationId: string) => {
    setSelectedConversation(conversationId)
    loadMessages(conversationId)
  }

  const handleSendMessage = async () => {
    if ((!messageInput.trim() && !attachment) || !selectedConversation || !workspaceId) return

    try {
      let attachmentUrl: string | undefined
      let attachmentType: string | undefined

      // Upload attachment first if present
      if (attachment) {
        setUploadingAttachment(true)
        try {
          const formData = new FormData()
          formData.append('file', attachment.file)

          const uploadResponse = await axios.post(
            `${API_URL}/attachments/upload?user_id=${userId}&is_voice_note=${attachment.type === 'audio'}`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          )

          attachmentUrl = uploadResponse.data.file_url
          attachmentType = uploadResponse.data.mime_type
          console.log('Attachment uploaded:', attachmentUrl)
        } catch (uploadError: any) {
          console.error('Failed to upload attachment:', uploadError)
          alert(uploadError.response?.data?.detail || 'Failed to upload attachment')
          setUploadingAttachment(false)
          return
        }
        setUploadingAttachment(false)
      }

      // Send message with or without attachment
      await axios.post(`${API_URL}/messages/messages/send`, {
        conversation_id: selectedConversation,
        workspace_id: workspaceId,
        message_text: messageInput || '',
        attachment_url: attachmentUrl,
        attachment_type: attachmentType
      })

      setMessageInput('')
      setAttachment(null)
      loadMessages(selectedConversation)
      if (workspaceId) loadConversations(workspaceId)
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to send message')
    }
  }

  // Handle file selection
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Determine file type
    let type: AttachmentPreview['type'] = 'file'
    if (file.type.startsWith('image/')) type = 'image'
    else if (file.type.startsWith('video/')) type = 'video'
    else if (file.type.startsWith('audio/')) type = 'audio'

    // Create preview URL
    const url = URL.createObjectURL(file)

    setAttachment({ file, url, type })

    // Reset input
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Clear attachment
  const clearAttachment = () => {
    if (attachment) {
      URL.revokeObjectURL(attachment.url)
      setAttachment(null)
    }
  }

  // Voice recording functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // Try different MIME types in order of Facebook compatibility
      // MP4/M4A is best for Facebook, then WebM with opus codec
      const mimeTypes = [
        { mime: 'audio/mp4', ext: '.m4a' },
        { mime: 'audio/aac', ext: '.aac' },
        { mime: 'audio/webm;codecs=opus', ext: '.webm' },
        { mime: 'audio/webm', ext: '.webm' },
        { mime: 'audio/ogg;codecs=opus', ext: '.ogg' },
      ]

      let selectedMimeType = 'audio/webm'
      let fileExtension = '.webm'

      for (const { mime, ext } of mimeTypes) {
        if (MediaRecorder.isTypeSupported(mime)) {
          selectedMimeType = mime
          fileExtension = ext
          console.log(`🎤 Using audio format: ${mime}`)
          break
        }
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType: selectedMimeType })

      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data)
        }
      }

      mediaRecorder.onstop = () => {
        const baseMimeType = selectedMimeType.split(';')[0] // Remove codec info
        const audioBlob = new Blob(audioChunksRef.current, { type: baseMimeType })
        const audioFile = new File([audioBlob], `voice_note_${Date.now()}${fileExtension}`, { type: baseMimeType })
        const url = URL.createObjectURL(audioBlob)

        setAttachment({ file: audioFile, url, type: 'audio' })

        // Stop all tracks
        stream.getTracks().forEach(track => track.stop())
      }

      mediaRecorderRef.current = mediaRecorder
      mediaRecorder.start()
      setIsRecording(true)
      setRecordingTime(0)

      // Start timer
      recordingTimerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1)
      }, 1000)
    } catch (error) {
      console.error('Failed to start recording:', error)
      alert('Could not access microphone. Please allow microphone access.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)

      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current)
        recordingTimerRef.current = null
      }
    }
  }

  const formatRecordingTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <DashboardLayout>
      <div className="bg-white rounded-lg shadow-md h-[calc(100vh-8rem)] flex">
        {/* Conversations List */}
        <div className="w-80 border-r border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold">Messages</h2>
            <div className="text-xs mt-1">
              <span className={`inline-block w-2 h-2 rounded-full mr-1 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
              {isConnected ? 'Connected' : 'Disconnected'}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-sm">
                No conversations yet. Connect your social accounts to start messaging.
              </div>
            ) : (
              conversations.map(conv => (
                <div
                  key={conv.id}
                  onClick={() => handleSelectConversation(conv.id)}
                  className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 ${selectedConversation === conv.id ? 'bg-blue-50' : ''}`}
                >
                  <div className="flex items-center gap-3">
                    {/* Profile Picture with proper fallback */}
                    <div className="flex-shrink-0 relative">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white text-sm font-semibold">
                        {(conv.participant_name || conv.participant_username || '?')[0].toUpperCase()}
                      </div>
                      {conv.participant_profile_pic && (
                        <img
                          src={getProxiedProfilePic(conv.participant_profile_pic)}
                          alt={conv.participant_name || 'Profile'}
                          className="w-10 h-10 rounded-full object-cover absolute inset-0"
                          onError={(e) => {
                            // Hide image on error, fallback avatar is already visible underneath
                            (e.target as HTMLImageElement).style.display = 'none'
                          }}
                        />
                      )}
                    </div>
                    {/* Name and Message */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm truncate">{conv.participant_name || conv.participant_username}</span>
                        {conv.platform && (
                          <span className="text-xs">{conv.platform === 'facebook' ? '📘' : '📷'}</span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500">@{conv.participant_username}</div>
                      {conv.last_message && (
                        <div className="text-xs text-gray-600 mt-1 truncate">{conv.last_message}</div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 flex flex-col">
          {selectedConversation ? (
            <>
              {/* Messages Header */}
              <div className="p-4 border-b border-gray-200">
                {(() => {
                  const conv = conversations.find(c => c.id === selectedConversation)
                  return conv ? (
                    <div className="flex items-center gap-3">
                      {/* Profile Picture with proper fallback */}
                      <div className="flex-shrink-0 relative">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white text-sm font-semibold">
                          {(conv.participant_name || conv.participant_username || '?')[0].toUpperCase()}
                        </div>
                        {conv.participant_profile_pic && (
                          <img
                            src={getProxiedProfilePic(conv.participant_profile_pic)}
                            alt={conv.participant_name || 'Profile'}
                            className="w-10 h-10 rounded-full object-cover absolute inset-0"
                            onError={(e) => {
                              (e.target as HTMLImageElement).style.display = 'none'
                            }}
                          />
                        )}
                      </div>
                      {/* Name and Platform */}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{conv.participant_name || conv.participant_username}</span>
                          {conv.platform && (
                            <span className="text-sm">{conv.platform === 'facebook' ? '📘' : '📷'}</span>
                          )}
                        </div>
                        <div className="text-xs text-gray-500">@{conv.participant_username}</div>
                      </div>
                    </div>
                  ) : null
                })()}
              </div>

              {/* Messages List */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {loading ? (
                  <div className="text-center text-gray-500">Loading...</div>
                ) : messages.length === 0 ? (
                  <div className="text-center text-gray-500">No messages yet</div>
                ) : (
                  <>
                    {messages.map(msg => (
                      <div key={msg.id} className={`flex ${msg.direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-sm rounded-lg overflow-hidden ${msg.direction === 'outgoing' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-900'}`}>
                          {/* Image Attachment */}
                          {msg.attachment_url && (msg.message_type === 'image' || msg.attachment_type?.startsWith('image/')) && (
                            <div className="relative">
                              <a href={getProxiedMediaUrl(msg.attachment_url)} target="_blank" rel="noopener noreferrer">
                                <img
                                  src={getProxiedMediaUrl(msg.attachment_url)}
                                  alt="Image attachment"
                                  className="max-w-full max-h-64 object-contain cursor-pointer hover:opacity-90"
                                  onError={(e) => {
                                    // Replace with a styled placeholder on error
                                    const target = e.target as HTMLImageElement
                                    target.onerror = null // Prevent infinite loop
                                    target.style.display = 'none'
                                    // Show fallback div
                                    const fallback = target.nextElementSibling as HTMLElement
                                    if (fallback) fallback.style.display = 'flex'
                                  }}
                                />
                                <div
                                  className="hidden w-48 h-32 bg-gray-100 rounded items-center justify-center text-gray-400 text-sm"
                                  style={{ display: 'none' }}
                                >
                                  <div className="text-center">
                                    <div className="text-2xl mb-1">🖼️</div>
                                    <div>Image expired</div>
                                  </div>
                                </div>
                              </a>
                            </div>
                          )}

                          {/* Video Attachment */}
                          {msg.attachment_url && (msg.message_type === 'video' || msg.attachment_type?.startsWith('video/')) && (
                            <video
                              src={getProxiedMediaUrl(msg.attachment_url)}
                              controls
                              className="max-w-full max-h-64"
                              preload="metadata"
                            >
                              Your browser does not support video playback.
                            </video>
                          )}

                          {/* Audio/Voice Note Attachment */}
                          {msg.attachment_url && (msg.message_type === 'audio' || msg.attachment_type?.startsWith('audio/')) && (
                            <div className="px-4 py-2">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-lg">🎤</span>
                                <span className="text-xs font-medium">Voice Message</span>
                              </div>
                              <audio
                                src={getProxiedMediaUrl(msg.attachment_url)}
                                controls
                                className="w-full h-8"
                                preload="metadata"
                              >
                                Your browser does not support audio playback.
                              </audio>
                            </div>
                          )}

                          {/* File Attachment */}
                          {msg.attachment_url && msg.message_type === 'file' && !msg.attachment_type?.startsWith('image/') && !msg.attachment_type?.startsWith('video/') && !msg.attachment_type?.startsWith('audio/') && (
                            <div className="px-4 py-2">
                              <a
                                href={getProxiedMediaUrl(msg.attachment_url)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={`flex items-center gap-2 ${msg.direction === 'outgoing' ? 'text-blue-100 hover:text-white' : 'text-blue-600 hover:text-blue-800'}`}
                              >
                                <span className="text-lg">📎</span>
                                <span className="text-sm underline">{msg.attachment_filename || 'Download File'}</span>
                              </a>
                            </div>
                          )}

                          {/* Text Content */}
                          {(msg.message_text || msg.content) && (
                            <div className="px-4 py-2">
                              <div className="text-sm whitespace-pre-wrap">{msg.message_text || msg.content}</div>
                            </div>
                          )}

                          {/* Timestamp */}
                          <div className={`px-4 pb-2 text-xs ${msg.direction === 'outgoing' ? 'text-blue-100' : 'text-gray-500'}`}>
                            {formatTime(msg.created_at)}
                          </div>
                        </div>
                      </div>
                    ))}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {/* Message Input */}
              <div className="p-4 border-t border-gray-200">
                {/* Attachment Preview */}
                {attachment && (
                  <div className="mb-3 p-3 bg-gray-50 rounded-lg relative">
                    <button
                      onClick={clearAttachment}
                      className="absolute top-1 right-1 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-sm hover:bg-red-600"
                    >
                      ×
                    </button>
                    {attachment.type === 'image' && (
                      <img src={attachment.url} alt="Preview" className="max-h-32 rounded" />
                    )}
                    {attachment.type === 'video' && (
                      <video src={attachment.url} className="max-h-32 rounded" controls />
                    )}
                    {attachment.type === 'audio' && (
                      <div className="flex items-center gap-2">
                        <span className="text-lg">🎤</span>
                        <audio src={attachment.url} controls className="h-8" />
                      </div>
                    )}
                    {attachment.type === 'file' && (
                      <div className="flex items-center gap-2 text-gray-600">
                        <span className="text-lg">📎</span>
                        <span className="text-sm">{attachment.file.name}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Recording Indicator */}
                {isRecording && (
                  <div className="mb-3 p-3 bg-red-50 rounded-lg flex items-center gap-3">
                    <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                    <span className="text-red-600 font-medium">Recording... {formatRecordingTime(recordingTime)}</span>
                    <button
                      onClick={stopRecording}
                      className="ml-auto px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
                    >
                      Stop
                    </button>
                  </div>
                )}

                <div className="flex gap-2 items-center">
                  {/* Hidden File Input */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    accept="image/*,video/*,audio/*,.pdf,.doc,.docx"
                    className="hidden"
                  />

                  {/* Attachment Button */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isRecording || uploadingAttachment}
                    className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg disabled:opacity-50"
                    title="Attach file"
                  >
                    📎
                  </button>

                  {/* Voice Note Button */}
                  {(() => {
                    const currentConv = conversations.find(c => c.id === selectedConversation)
                    const isInstagram = currentConv?.platform === 'instagram'
                    return (
                      <button
                        onClick={isRecording ? stopRecording : startRecording}
                        disabled={uploadingAttachment || !!attachment || isInstagram}
                        className={`p-2 rounded-lg ${isRecording ? 'text-red-500 bg-red-50' : isInstagram ? 'text-gray-300 cursor-not-allowed' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'} disabled:opacity-50`}
                        title={isInstagram ? "Voice notes not supported on Instagram" : isRecording ? "Stop recording" : "Record voice note"}
                      >
                        🎤
                      </button>
                    )
                  })()}

                  {/* Text Input */}
                  <input
                    type="text"
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && !isRecording && handleSendMessage()}
                    placeholder={attachment ? "Add a caption..." : "Type a message..."}
                    disabled={isRecording}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  />

                  {/* Send Button */}
                  <button
                    onClick={handleSendMessage}
                    disabled={isRecording || uploadingAttachment || (!messageInput.trim() && !attachment)}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {uploadingAttachment ? '...' : 'Send'}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <div className="text-4xl mb-2">💬</div>
                <div>Select a conversation to start messaging</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
