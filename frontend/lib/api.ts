import axios from 'axios'

const API_URL = 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

export interface User {
  id: number
  username: string
  email: string | null
  created_at: string
  updated_at: string
}

export interface ConnectedAccount {
  id: number
  platform: string
  platform_user_id: string
  platform_username: string | null
  page_id: string | null
  page_name: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  platform: string
  conversation_id: string
  message_id: string
  sender_id: string
  recipient_id: string
  direction: 'incoming' | 'outgoing'
  message_type: 'text' | 'image' | 'video' | 'audio' | 'file' | 'sticker' | 'location'
  content: string | null
  attachment_url: string | null
  attachment_type: string | null
  attachment_filename: string | null
  thumbnail_url: string | null
  status: 'sent' | 'delivered' | 'read' | 'failed'
  created_at: string
  updated_at: string
}

export interface Conversation {
  conversation_id: string
  platform: string
  participant_id: string
  participant_name: string | null
  participant_username: string | null
  participant_profile_pic: string | null
  last_message: Message | null
  unread_count: number
  ai_enabled: boolean
}

export interface AISettings {
  id?: number
  user_id: number
  ai_provider: 'openai' | 'anthropic'
  api_key: string | null
  model_name: string
  system_prompt: string | null
  response_tone: string
  max_tokens: number
  temperature: number
  context_messages_count: number
  created_at?: string
  updated_at?: string
}

// User APIs
export const createUser = async (username: string, email?: string) => {
  const response = await axios.post<User>(`${API_URL}/users/`, {
    username,
    email: email || null,
  })
  return response.data
}

export const getUser = async (userId: number) => {
  const response = await axios.get<User>(`${API_URL}/users/${userId}`)
  return response.data
}

// Account APIs
export const getConnectedAccounts = async (userId: number) => {
  const response = await axios.get<ConnectedAccount[]>(
    `${API_URL}/accounts/${userId}`
  )
  return response.data
}

export const disconnectAccount = async (accountId: number) => {
  const response = await axios.delete(`${API_URL}/accounts/${accountId}`)
  return response.data
}

export const getFacebookAuthUrl = async (userId: number) => {
  const response = await axios.get<{ auth_url: string }>(
    `${API_URL}/auth/facebook/login?user_id=${userId}`
  )
  return response.data.auth_url
}

export const getInstagramAuthUrl = async (userId: number) => {
  const response = await axios.get<{ auth_url: string }>(
    `${API_URL}/auth/instagram/login?user_id=${userId}`
  )
  return response.data.auth_url
}

// Message APIs
export const getConversations = async (
  userId: number,
  platform?: string
) => {
  const params = new URLSearchParams({ user_id: userId.toString() })
  if (platform) params.append('platform', platform)

  const response = await axios.get<Conversation[]>(
    `${API_URL}/messages/conversations?${params}`
  )
  return response.data
}

export const getConversationMessages = async (
  conversationId: string,
  userId: number,
  limit = 50,
  offset = 0
) => {
  const response = await axios.get<Message[]>(
    `${API_URL}/messages/conversation/${conversationId}?user_id=${userId}&limit=${limit}&offset=${offset}`
  )
  return response.data
}

export const sendMessage = async (
  userId: number,
  accountId: number,
  platform: string,
  recipientId: string,
  content: string
) => {
  const response = await axios.post<Message>(
    `${API_URL}/messages/send?user_id=${userId}&account_id=${accountId}`,
    {
      recipient_id: recipientId,
      content,
      platform,
    }
  )
  return response.data
}

export const syncMessages = async (userId: number, accountId: number) => {
  const response = await axios.get(
    `${API_URL}/messages/sync?user_id=${userId}&account_id=${accountId}`
  )
  return response.data
}

// AI APIs
export const toggleAI = async (
  conversationId: string,
  userId: number,
  aiEnabled: boolean
) => {
  const response = await axios.post(
    `${API_URL}/ai/conversations/${conversationId}/toggle?user_id=${userId}`,
    { ai_enabled: aiEnabled }
  )
  return response.data
}

export const getAIStatus = async (conversationId: string, userId: number) => {
  const response = await axios.get(
    `${API_URL}/ai/conversations/${conversationId}/status?user_id=${userId}`
  )
  return response.data
}

export const getAISettings = async (userId: number) => {
  const response = await axios.get<AISettings>(
    `${API_URL}/ai/settings?user_id=${userId}`
  )
  return response.data
}

export const updateAISettings = async (userId: number, settings: Partial<AISettings>) => {
  const response = await axios.post<AISettings>(
    `${API_URL}/ai/settings?user_id=${userId}`,
    settings
  )
  return response.data
}

export const testAIResponse = async (
  userId: number,
  conversationId: string,
  testMessage: string
) => {
  const response = await axios.post<{ response: string }>(
    `${API_URL}/ai/test?user_id=${userId}`,
    {
      conversation_id: conversationId,
      message: testMessage,
    }
  )
  return response.data
}
