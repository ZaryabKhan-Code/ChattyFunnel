const API_URL = 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

export interface AIBotTrigger {
  id: number
  bot_id: number
  trigger_type: 'keyword' | 'sentiment' | 'time_based' | 'always'
  trigger_config: Record<string, any>
  priority: number
  is_active: boolean
}

export interface AIBot {
  id: number
  workspace_id: number
  name: string
  bot_type: 'workspace_default' | 'funnel_specific' | 'conversation_override'
  ai_provider: 'openai' | 'anthropic' | 'custom'
  ai_model: string
  system_prompt: string
  temperature: number
  max_tokens: number
  auto_respond: boolean
  response_delay_seconds: number
  max_messages_per_conversation: number | null
  knowledge_base_url: string | null
  context_window_messages: number
  is_active: boolean
  created_at: string
  updated_at: string
  triggers: AIBotTrigger[]
}

export interface ConversationAISettings {
  id: number
  conversation_id: string
  workspace_id: number
  ai_enabled: boolean
  assigned_bot_id: number | null
  funnel_id: number | null
  override_workspace_default: boolean
  created_at: string
  updated_at: string
}

export async function getAIBots(
  workspaceId: number,
  userId: number,
  botType?: string,
  includeInactive = false
): Promise<AIBot[]> {
  let url = `${API_URL}/ai-bots?workspace_id=${workspaceId}&user_id=${userId}&include_inactive=${includeInactive}`
  if (botType) url += `&bot_type=${botType}`

  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch AI bots')
  return response.json()
}

export async function getAIBot(botId: number, userId: number): Promise<AIBot> {
  const response = await fetch(`${API_URL}/ai-bots/${botId}?user_id=${userId}`)
  if (!response.ok) throw new Error('Failed to fetch AI bot')
  return response.json()
}

export async function createAIBot(
  workspaceId: number,
  userId: number,
  data: {
    name: string
    bot_type: string
    ai_provider?: string
    ai_model?: string
    system_prompt: string
    temperature?: number
    max_tokens?: number
    auto_respond?: boolean
    response_delay_seconds?: number
    max_messages_per_conversation?: number | null
    knowledge_base_url?: string | null
    context_window_messages?: number
    is_active?: boolean
    triggers?: Partial<AIBotTrigger>[]
  }
): Promise<AIBot> {
  const response = await fetch(`${API_URL}/ai-bots?workspace_id=${workspaceId}&user_id=${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to create AI bot')
  return response.json()
}

export async function updateAIBot(
  botId: number,
  userId: number,
  data: {
    name?: string
    bot_type?: string
    ai_provider?: string
    ai_model?: string
    system_prompt?: string
    temperature?: number
    max_tokens?: number
    auto_respond?: boolean
    response_delay_seconds?: number
    max_messages_per_conversation?: number | null
    knowledge_base_url?: string | null
    context_window_messages?: number
    is_active?: boolean
  }
): Promise<AIBot> {
  const response = await fetch(`${API_URL}/ai-bots/${botId}?user_id=${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to update AI bot')
  return response.json()
}

export async function deleteAIBot(botId: number, userId: number): Promise<void> {
  const response = await fetch(`${API_URL}/ai-bots/${botId}?user_id=${userId}`, {
    method: 'DELETE',
  })
  if (!response.ok) throw new Error('Failed to delete AI bot')
}

// Bot Triggers
export async function createBotTrigger(
  botId: number,
  userId: number,
  data: {
    trigger_type: string
    trigger_config: Record<string, any>
    priority?: number
    is_active?: boolean
  }
): Promise<AIBotTrigger> {
  const response = await fetch(`${API_URL}/ai-bots/${botId}/triggers?user_id=${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to create trigger')
  return response.json()
}

export async function updateBotTrigger(
  botId: number,
  triggerId: number,
  userId: number,
  data: {
    trigger_type?: string
    trigger_config?: Record<string, any>
    priority?: number
    is_active?: boolean
  }
): Promise<AIBotTrigger> {
  const response = await fetch(
    `${API_URL}/ai-bots/${botId}/triggers/${triggerId}?user_id=${userId}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  if (!response.ok) throw new Error('Failed to update trigger')
  return response.json()
}

export async function deleteBotTrigger(
  botId: number,
  triggerId: number,
  userId: number
): Promise<void> {
  const response = await fetch(
    `${API_URL}/ai-bots/${botId}/triggers/${triggerId}?user_id=${userId}`,
    {
      method: 'DELETE',
    }
  )
  if (!response.ok) throw new Error('Failed to delete trigger')
}

// Conversation AI Settings
export async function getConversationAISettings(
  conversationId: string,
  workspaceId: number,
  userId: number
): Promise<ConversationAISettings> {
  const response = await fetch(
    `${API_URL}/ai-bots/conversation-settings/${conversationId}?workspace_id=${workspaceId}&user_id=${userId}`
  )
  if (!response.ok) throw new Error('Failed to fetch conversation AI settings')
  return response.json()
}

export async function updateConversationAISettings(
  conversationId: string,
  workspaceId: number,
  userId: number,
  data: {
    ai_enabled?: boolean
    assigned_bot_id?: number | null
    override_workspace_default?: boolean
  }
): Promise<ConversationAISettings> {
  const response = await fetch(
    `${API_URL}/ai-bots/conversation-settings/${conversationId}?workspace_id=${workspaceId}&user_id=${userId}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  if (!response.ok) throw new Error('Failed to update conversation AI settings')
  return response.json()
}
