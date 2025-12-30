const API_URL = 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

export interface FunnelStep {
  id: number
  funnel_id: number
  name: string
  step_order: number
  step_type: 'send_message' | 'delay' | 'condition' | 'tag' | 'assign_human' | 'ai_response'
  step_config: Record<string, any>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Funnel {
  id: number
  workspace_id: number
  name: string
  description: string | null
  trigger_type: 'keyword' | 'new_conversation' | 'tag' | 'custom'
  trigger_config: Record<string, any>
  is_active: boolean
  priority: number
  created_at: string
  updated_at: string
  steps: FunnelStep[]
  enrollment_count?: number
}

export interface FunnelEnrollment {
  id: number
  funnel_id: number
  conversation_id: string
  current_step: number
  status: 'active' | 'completed' | 'paused' | 'exited'
  enrolled_at: string
  completed_at: string | null
  next_step_at: string | null
  metadata: Record<string, any>
}

export async function getFunnels(
  workspaceId: number,
  userId: number,
  includeInactive = false
): Promise<Funnel[]> {
  const response = await fetch(
    `${API_URL}/funnels?workspace_id=${workspaceId}&user_id=${userId}&include_inactive=${includeInactive}`
  )
  if (!response.ok) throw new Error('Failed to fetch funnels')
  return response.json()
}

export async function getFunnel(funnelId: number, userId: number): Promise<Funnel> {
  const response = await fetch(`${API_URL}/funnels/${funnelId}?user_id=${userId}`)
  if (!response.ok) throw new Error('Failed to fetch funnel')
  return response.json()
}

export async function createFunnel(
  workspaceId: number,
  userId: number,
  data: {
    name: string
    description?: string
    trigger_type: string
    trigger_config?: Record<string, any>
    is_active?: boolean
    priority?: number
    steps?: Partial<FunnelStep>[]
  }
): Promise<Funnel> {
  const response = await fetch(
    `${API_URL}/funnels?workspace_id=${workspaceId}&user_id=${userId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  if (!response.ok) throw new Error('Failed to create funnel')
  return response.json()
}

export async function updateFunnel(
  funnelId: number,
  userId: number,
  data: {
    name?: string
    description?: string
    trigger_type?: string
    trigger_config?: Record<string, any>
    is_active?: boolean
    priority?: number
  }
): Promise<Funnel> {
  const response = await fetch(`${API_URL}/funnels/${funnelId}?user_id=${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to update funnel')
  return response.json()
}

export async function deleteFunnel(funnelId: number, userId: number): Promise<void> {
  const response = await fetch(`${API_URL}/funnels/${funnelId}?user_id=${userId}`, {
    method: 'DELETE',
  })
  if (!response.ok) throw new Error('Failed to delete funnel')
}

// Funnel Steps
export async function getFunnelSteps(funnelId: number, userId: number): Promise<FunnelStep[]> {
  const response = await fetch(`${API_URL}/funnels/${funnelId}/steps?user_id=${userId}`)
  if (!response.ok) throw new Error('Failed to fetch funnel steps')
  return response.json()
}

export async function createFunnelStep(
  funnelId: number,
  userId: number,
  data: {
    name: string
    step_order: number
    step_type: string
    step_config: Record<string, any>
    is_active?: boolean
  }
): Promise<FunnelStep> {
  const response = await fetch(`${API_URL}/funnels/${funnelId}/steps?user_id=${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to create step')
  return response.json()
}

export async function updateFunnelStep(
  funnelId: number,
  stepId: number,
  userId: number,
  data: {
    name?: string
    step_order?: number
    step_type?: string
    step_config?: Record<string, any>
    is_active?: boolean
  }
): Promise<FunnelStep> {
  const response = await fetch(
    `${API_URL}/funnels/${funnelId}/steps/${stepId}?user_id=${userId}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  if (!response.ok) throw new Error('Failed to update step')
  return response.json()
}

export async function deleteFunnelStep(
  funnelId: number,
  stepId: number,
  userId: number
): Promise<void> {
  const response = await fetch(
    `${API_URL}/funnels/${funnelId}/steps/${stepId}?user_id=${userId}`,
    {
      method: 'DELETE',
    }
  )
  if (!response.ok) throw new Error('Failed to delete step')
}

// Funnel Enrollments
export async function enrollConversation(
  userId: number,
  data: { funnel_id: number; conversation_id: string }
): Promise<FunnelEnrollment> {
  const response = await fetch(`${API_URL}/funnels/enrollments?user_id=${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to enroll conversation')
  return response.json()
}

export async function getConversationEnrollments(
  conversationId: string,
  workspaceId: number,
  userId: number
): Promise<FunnelEnrollment[]> {
  const response = await fetch(
    `${API_URL}/funnels/enrollments/${conversationId}?workspace_id=${workspaceId}&user_id=${userId}`
  )
  if (!response.ok) throw new Error('Failed to fetch enrollments')
  return response.json()
}

export async function updateEnrollment(
  enrollmentId: number,
  userId: number,
  data: { status?: string; current_step?: number }
): Promise<FunnelEnrollment> {
  const response = await fetch(`${API_URL}/funnels/enrollments/${enrollmentId}?user_id=${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Failed to update enrollment')
  return response.json()
}
