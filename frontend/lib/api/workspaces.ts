const API_URL = 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

export interface Workspace {
  id: number
  owner_id: number
  name: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  member_count?: number
  account_count?: number
}

export interface WorkspaceMember {
  id: number
  workspace_id: number
  user_id: number
  role: 'owner' | 'admin' | 'member'
  permissions: Record<string, any>
  created_at: string
  username?: string
}

export interface ConversationTag {
  id: number
  workspace_id: number
  conversation_id: string
  tag: string
  created_at: string
}

export async function getWorkspaces(userId: number): Promise<Workspace[]> {
  const response = await fetch(`${API_URL}/workspaces?user_id=${userId}`)
  if (!response.ok) throw new Error('Failed to fetch workspaces')
  return response.json()
}

export async function getWorkspace(workspaceId: number, userId: number): Promise<Workspace> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}?user_id=${userId}`)
  if (!response.ok) throw new Error('Failed to fetch workspace')
  return response.json()
}

export async function createWorkspace(
  userId: number,
  data: { name: string; description?: string }
): Promise<Workspace> {
  const response = await fetch(`${API_URL}/workspaces?user_id=${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to create workspace')
  return response.json()
}

export async function updateWorkspace(
  workspaceId: number,
  userId: number,
  data: { name?: string; description?: string; is_active?: boolean }
): Promise<Workspace> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}?user_id=${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to update workspace')
  return response.json()
}

export async function deleteWorkspace(workspaceId: number, userId: number): Promise<void> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}?user_id=${userId}`, {
    method: 'DELETE',
  })
  if (!response.ok) throw new Error('Failed to delete workspace')
}

// Workspace Members
export async function getWorkspaceMembers(
  workspaceId: number,
  userId: number
): Promise<WorkspaceMember[]> {
  const response = await fetch(
    `${API_URL}/workspaces/${workspaceId}/members?user_id=${userId}`
  )
  if (!response.ok) throw new Error('Failed to fetch members')
  return response.json()
}

export async function addWorkspaceMember(
  workspaceId: number,
  userId: number,
  data: { user_id: number; role?: string; permissions?: Record<string, any> }
): Promise<WorkspaceMember> {
  const response = await fetch(
    `${API_URL}/workspaces/${workspaceId}/members?user_id=${userId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  if (!response.ok) throw new Error('Failed to add member')
  return response.json()
}

export async function updateWorkspaceMember(
  workspaceId: number,
  memberId: number,
  userId: number,
  data: { role?: string; permissions?: Record<string, any> }
): Promise<WorkspaceMember> {
  const response = await fetch(
    `${API_URL}/workspaces/${workspaceId}/members/${memberId}?user_id=${userId}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  if (!response.ok) throw new Error('Failed to update member')
  return response.json()
}

export async function removeWorkspaceMember(
  workspaceId: number,
  memberId: number,
  userId: number
): Promise<void> {
  const response = await fetch(
    `${API_URL}/workspaces/${workspaceId}/members/${memberId}?user_id=${userId}`,
    {
      method: 'DELETE',
    }
  )
  if (!response.ok) throw new Error('Failed to remove member')
}

// Conversation Tags
export async function addConversationTag(
  workspaceId: number,
  userId: number,
  data: { conversation_id: string; tag: string }
): Promise<ConversationTag> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/tags?user_id=${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to add tag')
  return response.json()
}

export async function getConversationTags(
  workspaceId: number,
  conversationId: string,
  userId: number
): Promise<ConversationTag[]> {
  const response = await fetch(
    `${API_URL}/workspaces/${workspaceId}/tags/${conversationId}?user_id=${userId}`
  )
  if (!response.ok) throw new Error('Failed to fetch tags')
  return response.json()
}

export async function removeConversationTag(
  workspaceId: number,
  tagId: number,
  userId: number
): Promise<void> {
  const response = await fetch(
    `${API_URL}/workspaces/${workspaceId}/tags/${tagId}?user_id=${userId}`,
    {
      method: 'DELETE',
    }
  )
  if (!response.ok) throw new Error('Failed to remove tag')
}
