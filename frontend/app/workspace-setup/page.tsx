'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

interface Workspace {
  id: number
  name: string
  description: string
}

export default function WorkspaceSetup() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [workspaceName, setWorkspaceName] = useState('')
  const [workspaceDescription, setWorkspaceDescription] = useState('')
  const router = useRouter()

  useEffect(() => {
    loadWorkspaces()
  }, [])

  const loadWorkspaces = async () => {
    const userId = localStorage.getItem('userId')
    if (!userId) {
      router.push('/')
      return
    }

    try {
      const response = await axios.get(`${API_URL}/workspaces?user_id=${userId}`)
      setWorkspaces(response.data)

      // If no workspaces, show create form
      if (response.data.length === 0) {
        setShowCreateForm(true)
      }
    } catch (error) {
      console.error('Failed to load workspaces:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)

    const userId = localStorage.getItem('userId')

    try {
      const response = await axios.post(`${API_URL}/workspaces?user_id=${userId}`, {
        name: workspaceName,
        description: workspaceDescription,
      })

      localStorage.setItem('workspaceId', response.data.id.toString())
      router.push('/dashboard')
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to create workspace')
    } finally {
      setCreating(false)
    }
  }

  const handleSelectWorkspace = (workspaceId: number) => {
    localStorage.setItem('workspaceId', workspaceId.toString())
    router.push('/dashboard')
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-600">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-center mb-8">Workspaces</h1>

        {!showCreateForm && workspaces.length > 0 && (
          <div className="mb-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold mb-4">Your Workspaces</h2>
              <div className="space-y-3">
                {workspaces.map((workspace) => (
                  <div
                    key={workspace.id}
                    onClick={() => handleSelectWorkspace(workspace.id)}
                    className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 cursor-pointer transition"
                  >
                    <h3 className="font-semibold text-lg">{workspace.name}</h3>
                    {workspace.description && (
                      <p className="text-gray-600 text-sm mt-1">{workspace.description}</p>
                    )}
                  </div>
                ))}
              </div>
              <button
                onClick={() => setShowCreateForm(true)}
                className="mt-4 w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700"
              >
                Create New Workspace
              </button>
            </div>
          </div>
        )}

        {showCreateForm && (
          <div className="bg-white rounded-lg shadow-md p-6 max-w-md mx-auto">
            <h2 className="text-xl font-semibold mb-4">
              {workspaces.length === 0 ? 'Create Your First Workspace' : 'Create New Workspace'}
            </h2>
            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Workspace Name
                </label>
                <input
                  type="text"
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="My Workspace"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description (optional)
                </label>
                <textarea
                  value={workspaceDescription}
                  onChange={(e) => setWorkspaceDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Description of your workspace"
                  rows={3}
                />
              </div>

              <button
                type="submit"
                disabled={creating}
                className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
              >
                {creating ? 'Creating...' : 'Create Workspace'}
              </button>

              {workspaces.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="w-full bg-gray-200 text-gray-700 py-2 px-4 rounded-md hover:bg-gray-300"
                >
                  Cancel
                </button>
              )}
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
