'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import DashboardLayout from '@/components/DashboardLayout'
import { useWebSocket } from '@/hooks/useWebSocket'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

interface Conversation {
  id: string
  participant_name: string
  participant_username: string
  last_message?: string
  updated_at?: string
}

interface Message {
  id: number
  message_text: string
  direction: string
  created_at: string
  sender_id: string
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

  // WebSocket hook
  const { isConnected, lastMessage, sendMessage: wsSendMessage } = useWebSocket(userId)

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
      // Reload conversations and messages if current conversation
      if (workspaceId) {
        loadConversations(workspaceId)
      }
      if (selectedConversation === lastMessage.data.conversation_id) {
        loadMessages(selectedConversation)
      }
    }
  }, [lastMessage, workspaceId, selectedConversation])

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
    if (!messageInput.trim() || !selectedConversation || !workspaceId) return

    try {
      await axios.post(`${API_URL}/messages/messages/send`, {
        conversation_id: selectedConversation,
        workspace_id: workspaceId,
        message_text: messageInput
      })

      setMessageInput('')
      loadMessages(selectedConversation)
      if (workspaceId) loadConversations(workspaceId)
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to send message')
    }
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
                  <div className="font-semibold text-sm">{conv.participant_name}</div>
                  <div className="text-xs text-gray-500">@{conv.participant_username}</div>
                  {conv.last_message && (
                    <div className="text-xs text-gray-600 mt-1 truncate">{conv.last_message}</div>
                  )}
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
                <div className="font-semibold">
                  {conversations.find(c => c.id === selectedConversation)?.participant_name}
                </div>
                <div className="text-xs text-gray-500">
                  @{conversations.find(c => c.id === selectedConversation)?.participant_username}
                </div>
              </div>

              {/* Messages List */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {loading ? (
                  <div className="text-center text-gray-500">Loading...</div>
                ) : messages.length === 0 ? (
                  <div className="text-center text-gray-500">No messages yet</div>
                ) : (
                  messages.map(msg => (
                    <div key={msg.id} className={`flex ${msg.direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-xs px-4 py-2 rounded-lg ${msg.direction === 'outgoing' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-900'}`}>
                        <div className="text-sm">{msg.message_text}</div>
                        <div className={`text-xs mt-1 ${msg.direction === 'outgoing' ? 'text-blue-100' : 'text-gray-500'}`}>
                          {formatTime(msg.created_at)}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Message Input */}
              <div className="p-4 border-t border-gray-200">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="Type a message..."
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={handleSendMessage}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Send
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
