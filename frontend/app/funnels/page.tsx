'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import DashboardLayout from '@/components/DashboardLayout'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

interface Funnel {
  id: number
  name: string
  description: string
}

interface Conversation {
  id: string
  participant_name: string
  participant_username: string
  funnel_id?: number | null
}

export default function FunnelsPage() {
  const [userId, setUserId] = useState<number | null>(null)
  const [workspaceId, setWorkspaceId] = useState<number | null>(null)
  const [funnels, setFunnels] = useState<Funnel[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [funnelName, setFunnelName] = useState('')
  const [funnelDescription, setFunnelDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const uid = localStorage.getItem('userId')
    const wid = localStorage.getItem('workspaceId')

    if (!uid || !wid) {
      router.push('/')
      return
    }

    setUserId(parseInt(uid))
    setWorkspaceId(parseInt(wid))
    loadData(parseInt(wid))
  }, [router])

  const loadData = async (wid: number) => {
    setLoading(true)
    try {
      const uid = localStorage.getItem('userId')
      if (!uid) return

      // Load funnels
      const funnelsRes = await axios.get(`${API_URL}/funnels?workspace_id=${wid}&user_id=${uid}`)
      setFunnels(funnelsRes.data)

      // Load conversations
      const convsRes = await axios.get(`${API_URL}/messages/conversations?workspace_id=${wid}`)

      // Get funnel assignment for each conversation
      const conversationsWithFunnels = await Promise.all(
        convsRes.data.map(async (conv: any) => {
          try {
            const settingsRes = await axios.get(`${API_URL}/messages/conversations/${conv.id}/ai-settings`)
            return { ...conv, funnel_id: settingsRes.data.funnel_id }
          } catch {
            return { ...conv, funnel_id: null }
          }
        })
      )

      setConversations(conversationsWithFunnels)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateFunnel = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceId || !userId) return

    try {
      await axios.post(`${API_URL}/funnels?workspace_id=${workspaceId}&user_id=${userId}`, {
        name: funnelName,
        description: funnelDescription,
        trigger_type: 'custom',
        trigger_config: {},
        is_active: true,
        priority: 0,
        steps: []
      })

      setFunnelName('')
      setFunnelDescription('')
      setShowCreateModal(false)
      loadData(workspaceId)
    } catch (error: any) {
      console.error('Failed to create funnel:', error)
      alert(error.response?.data?.detail || 'Failed to create funnel')
    }
  }

  const handleAssignToFunnel = async (conversationId: string, funnelId: number | null) => {
    try {
      await axios.post(`${API_URL}/messages/conversations/${conversationId}/funnel`, {
        funnel_id: funnelId
      })

      // Update local state
      setConversations(conversations.map(conv =>
        conv.id === conversationId ? { ...conv, funnel_id: funnelId } : conv
      ))
    } catch (error) {
      alert('Failed to assign conversation')
    }
  }

  const getConversationsForFunnel = (funnelId: number | null) => {
    return conversations.filter(conv => conv.funnel_id === funnelId)
  }

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-600">Loading...</div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Funnels</h1>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Create Funnel
          </button>
        </div>

        {/* Create Funnel Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
              <h2 className="text-xl font-bold mb-4">Create New Funnel</h2>
              <form onSubmit={handleCreateFunnel} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Funnel Name
                  </label>
                  <input
                    type="text"
                    value={funnelName}
                    onChange={(e) => setFunnelName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    value={funnelDescription}
                    onChange={(e) => setFunnelDescription(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={3}
                  />
                </div>

                <div className="flex gap-2">
                  <button
                    type="submit"
                    className="flex-1 bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
                  >
                    Create
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="flex-1 bg-gray-200 text-gray-700 py-2 rounded-md hover:bg-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Funnels Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Unassigned Column */}
          <div className="bg-gray-50 rounded-lg p-4 border-2 border-gray-300">
            <h3 className="font-semibold mb-3 text-gray-700">Unassigned</h3>
            <div className="space-y-2">
              {getConversationsForFunnel(null).map(conv => (
                <div key={conv.id} className="bg-white p-3 rounded shadow-sm">
                  <div className="font-medium text-sm">{conv.participant_name}</div>
                  <div className="text-xs text-gray-500">@{conv.participant_username}</div>
                  <select
                    onChange={(e) => handleAssignToFunnel(conv.id, e.target.value ? parseInt(e.target.value) : null)}
                    className="mt-2 w-full text-xs px-2 py-1 border rounded"
                    value=""
                  >
                    <option value="">Assign to funnel...</option>
                    {funnels.map(funnel => (
                      <option key={funnel.id} value={funnel.id}>{funnel.name}</option>
                    ))}
                  </select>
                </div>
              ))}
              {getConversationsForFunnel(null).length === 0 && (
                <div className="text-sm text-gray-500 text-center py-4">
                  No unassigned conversations
                </div>
              )}
            </div>
          </div>

          {/* Funnel Columns */}
          {funnels.map(funnel => (
            <div key={funnel.id} className="bg-blue-50 rounded-lg p-4 border-2 border-blue-300">
              <h3 className="font-semibold mb-1">{funnel.name}</h3>
              <p className="text-xs text-gray-600 mb-3">{funnel.description}</p>
              <div className="space-y-2">
                {getConversationsForFunnel(funnel.id).map(conv => (
                  <div key={conv.id} className="bg-white p-3 rounded shadow-sm">
                    <div className="font-medium text-sm">{conv.participant_name}</div>
                    <div className="text-xs text-gray-500">@{conv.participant_username}</div>
                    <button
                      onClick={() => handleAssignToFunnel(conv.id, null)}
                      className="mt-2 w-full text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
                    >
                      Remove from funnel
                    </button>
                  </div>
                ))}
                {getConversationsForFunnel(funnel.id).length === 0 && (
                  <div className="text-sm text-gray-500 text-center py-4">
                    No conversations
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {funnels.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <div className="text-4xl mb-2">🎯</div>
            <p>No funnels yet. Create one to get started!</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
