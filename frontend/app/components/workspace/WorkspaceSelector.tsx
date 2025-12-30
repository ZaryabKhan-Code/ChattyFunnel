'use client'

import { useState } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { createWorkspace } from '@/lib/api/workspaces'

export default function WorkspaceSelector({ userId }: { userId: number }) {
  const {selectedWorkspace, setSelectedWorkspace, workspaces, refreshWorkspaces } = useWorkspace()
  const [isCreating, setIsCreating] = useState(false)
  const [newWorkspaceName, setNewWorkspaceName] = useState('')

  const handleCreateWorkspace = async () => {
    if (!newWorkspaceName.trim()) return

    try {
      const workspace = await createWorkspace(userId, {
        name: newWorkspaceName,
        description: 'Workspace created from dashboard',
      })
      await refreshWorkspaces()
      setSelectedWorkspace(workspace)
      setNewWorkspaceName('')
      setIsCreating(false)
    } catch (error) {
      console.error('Failed to create workspace:', error)
      alert('Failed to create workspace')
    }
  }

  return (
    <div className="flex items-center gap-3">
      <label htmlFor="workspace-select" className="text-sm font-medium text-gray-700">
        Workspace:
      </label>

      <select
        id="workspace-select"
        value={selectedWorkspace?.id || ''}
        onChange={(e) => {
          const workspace = workspaces.find((w) => w.id === Number(e.target.value))
          setSelectedWorkspace(workspace || null)
        }}
        className="block w-64 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
      >
        {workspaces.length === 0 && (
          <option value="">No workspaces available</option>
        )}
        {workspaces.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>
            {workspace.name} ({workspace.account_count || 0} accounts)
          </option>
        ))}
      </select>

      {!isCreating ? (
        <button
          onClick={() => setIsCreating(true)}
          className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          + New
        </button>
      ) : (
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
            placeholder="Workspace name"
            className="block w-48 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleCreateWorkspace()
              if (e.key === 'Escape') {
                setIsCreating(false)
                setNewWorkspaceName('')
              }
            }}
            autoFocus
          />
          <button
            onClick={handleCreateWorkspace}
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Create
          </button>
          <button
            onClick={() => {
              setIsCreating(false)
              setNewWorkspaceName('')
            }}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Cancel
          </button>
        </div>
      )}

      {selectedWorkspace && (
        <a
          href="/workspaces"
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          Manage
        </a>
      )}
    </div>
  )
}
