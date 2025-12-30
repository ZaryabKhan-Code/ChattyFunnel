'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import DashboardLayout from '@/components/DashboardLayout'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

interface ConnectedAccount {
  id: number
  platform: string
  platform_username: string
  is_active: boolean
}

export default function Dashboard() {
  const [userId, setUserId] = useState<number | null>(null)
  const [workspaceId, setWorkspaceId] = useState<number | null>(null)
  const [connectedAccounts, setConnectedAccounts] = useState<ConnectedAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [disconnecting, setDisconnecting] = useState<number | null>(null)
  const router = useRouter()

  useEffect(() => {
    const storedUserId = localStorage.getItem('userId')
    const storedWorkspaceId = localStorage.getItem('workspaceId')

    if (!storedUserId || !storedWorkspaceId) {
      router.push('/')
      return
    }

    const uid = parseInt(storedUserId)
    const wid = parseInt(storedWorkspaceId)
    setUserId(uid)
    setWorkspaceId(wid)
    loadConnectedAccounts(uid, wid)

    // Check for OAuth success
    const params = new URLSearchParams(window.location.search)
    const success = params.get('success')
    if (success === 'facebook') {
      alert('✅ Facebook connected successfully!')
      window.history.replaceState({}, '', '/dashboard')
      loadConnectedAccounts(uid, wid)
    } else if (success === 'instagram') {
      alert('✅ Instagram connected successfully!')
      window.history.replaceState({}, '', '/dashboard')
      loadConnectedAccounts(uid, wid)
    }
  }, [router])

  const loadConnectedAccounts = async (uid: number, wid: number) => {
    try {
      const response = await fetch(`${API_URL}/accounts/${uid}?workspace_id=${wid}`)
      if (response.ok) {
        const accounts = await response.json()
        setConnectedAccounts(accounts.filter((acc: ConnectedAccount) => acc.is_active))
      }
    } catch (error) {
      console.error('Failed to load connected accounts:', error)
    } finally {
      setLoading(false)
    }
  }

  const disconnectAccount = async (accountId: number, platform: string) => {
    if (!confirm(`Are you sure you want to disconnect this ${platform} account?`)) {
      return
    }

    setDisconnecting(accountId)
    try {
      const response = await fetch(`${API_URL}/accounts/${accountId}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        alert(`${platform} disconnected successfully!`)
        if (userId && workspaceId) {
          loadConnectedAccounts(userId, workspaceId)
        }
      } else {
        alert('Failed to disconnect account. Please try again.')
      }
    } catch (error) {
      console.error('Failed to disconnect account:', error)
      alert('Failed to disconnect account. Please try again.')
    } finally {
      setDisconnecting(null)
    }
  }

  const connectFacebook = async () => {
    if (!userId) return

    try {
      const response = await fetch(`${API_URL}/auth/facebook/login?user_id=${userId}`)
      const data = await response.json()
      window.location.href = data.auth_url
    } catch (error) {
      alert('Failed to connect Facebook. Please try again.')
    }
  }

  const connectInstagram = async () => {
    if (!userId) return

    try {
      const response = await fetch(`${API_URL}/auth/instagram/login?user_id=${userId}`)
      const data = await response.json()
      window.location.href = data.auth_url
    } catch (error) {
      alert('Failed to connect Instagram. Please try again.')
    }
  }

  const hasFacebook = connectedAccounts.some(acc => acc.platform === 'facebook')
  const hasInstagram = connectedAccounts.some(acc => acc.platform === 'instagram')

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
        <div className="bg-white rounded-lg shadow-md p-6">
          <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

          {/* Connected Accounts Status */}
          <div className="mb-8">
            <h2 className="text-lg font-semibold mb-4">Social Accounts</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Facebook Status */}
              <div className={`p-4 rounded-lg border-2 ${hasFacebook ? 'border-green-500 bg-green-50' : 'border-gray-300 bg-gray-50'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-3xl">📘</div>
                    <div>
                      <div className="font-semibold">Facebook</div>
                      <div className="text-sm text-gray-600">
                        {hasFacebook ? (
                          <>
                            <span className="text-green-600 font-medium">✓ Connected</span>
                            <div className="text-xs mt-1">
                              {connectedAccounts.filter(acc => acc.platform === 'facebook').map(acc => (
                                <div key={acc.id} className="flex items-center gap-2">
                                  <span>{acc.platform_username}</span>
                                  <button
                                    onClick={() => disconnectAccount(acc.id, 'Facebook')}
                                    disabled={disconnecting === acc.id}
                                    className="text-red-500 hover:text-red-700 text-xs underline disabled:opacity-50"
                                  >
                                    {disconnecting === acc.id ? 'Disconnecting...' : 'Disconnect'}
                                  </button>
                                </div>
                              ))}
                            </div>
                          </>
                        ) : (
                          'Not connected'
                        )}
                      </div>
                    </div>
                  </div>
                  {!hasFacebook && (
                    <button
                      onClick={connectFacebook}
                      className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
                    >
                      Connect
                    </button>
                  )}
                </div>
              </div>

              {/* Instagram Status */}
              <div className={`p-4 rounded-lg border-2 ${hasInstagram ? 'border-green-500 bg-green-50' : 'border-gray-300 bg-gray-50'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-3xl">📷</div>
                    <div>
                      <div className="font-semibold">Instagram</div>
                      <div className="text-sm text-gray-600">
                        {hasInstagram ? (
                          <>
                            <span className="text-green-600 font-medium">✓ Connected</span>
                            <div className="text-xs mt-1">
                              {connectedAccounts.filter(acc => acc.platform === 'instagram').map(acc => (
                                <div key={acc.id} className="flex items-center gap-2">
                                  <span>@{acc.platform_username}</span>
                                  <button
                                    onClick={() => disconnectAccount(acc.id, 'Instagram')}
                                    disabled={disconnecting === acc.id}
                                    className="text-red-500 hover:text-red-700 text-xs underline disabled:opacity-50"
                                  >
                                    {disconnecting === acc.id ? 'Disconnecting...' : 'Disconnect'}
                                  </button>
                                </div>
                              ))}
                            </div>
                          </>
                        ) : (
                          'Not connected'
                        )}
                      </div>
                    </div>
                  </div>
                  {!hasInstagram && (
                    <button
                      onClick={connectInstagram}
                      className="px-4 py-2 bg-purple-600 text-white text-sm rounded-md hover:bg-purple-700"
                    >
                      Connect
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Navigation Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              onClick={() => router.push('/dashboard/messages')}
              className="p-6 bg-blue-50 hover:bg-blue-100 rounded-lg text-left transition"
            >
              <div className="text-3xl mb-2">💬</div>
              <div className="font-semibold text-lg">Messages</div>
              <div className="text-sm text-gray-600">Send and receive messages</div>
            </button>

            <button
              onClick={() => router.push('/funnels')}
              className="p-6 bg-green-50 hover:bg-green-100 rounded-lg text-left transition"
            >
              <div className="text-3xl mb-2">🎯</div>
              <div className="font-semibold text-lg">Funnels</div>
              <div className="text-sm text-gray-600">Manage conversation funnels</div>
            </button>

            <button
              onClick={() => router.push('/dashboard/bots')}
              className="p-6 bg-purple-50 hover:bg-purple-100 rounded-lg text-left transition"
            >
              <div className="text-3xl mb-2">🤖</div>
              <div className="font-semibold text-lg">AI Chatbot</div>
              <div className="text-sm text-gray-600">Configure AI responses</div>
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
