'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { Workspace, getWorkspaces } from '@/lib/api/workspaces'

interface WorkspaceContextType {
  selectedWorkspace: Workspace | null
  setSelectedWorkspace: (workspace: Workspace | null) => void
  workspaces: Workspace[]
  isLoading: boolean
  refreshWorkspaces: () => Promise<void>
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined)

export function WorkspaceProvider({
  children,
  userId,
}: {
  children: ReactNode
  userId: number | null
}) {
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const refreshWorkspaces = async () => {
    if (!userId) {
      setWorkspaces([])
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)
      const data = await getWorkspaces(userId)
      setWorkspaces(data)

      // Auto-select first workspace if none selected
      if (!selectedWorkspace && data.length > 0) {
        setSelectedWorkspace(data[0])
      }
    } catch (error) {
      console.error('Failed to load workspaces:', error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    refreshWorkspaces()
  }, [userId])

  return (
    <WorkspaceContext.Provider
      value={{
        selectedWorkspace,
        setSelectedWorkspace,
        workspaces,
        isLoading,
        refreshWorkspaces,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (context === undefined) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider')
  }
  return context
}
