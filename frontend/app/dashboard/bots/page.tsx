'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import DashboardLayout from '@/components/DashboardLayout'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

interface AIBot {
  id: number
  name: string
  ai_provider: string
  ai_model: string
  system_prompt: string
  is_active: boolean
}

export default function AIBots() {
  const [workspaceId, setWorkspaceId] = useState<number | null>(null)
  const [bots, setBots] = useState<AIBot[]>([])
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [botName, setBotName] = useState('')
  const [aiProvider, setAiProvider] = useState('openai')
  const [aiModel, setAiModel] = useState('gpt-4')
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful customer support assistant.')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const userId = localStorage.getItem('userId')
    const wid = localStorage.getItem('workspaceId')

    if (!userId || !wid) {
      router.push('/')
      return
    }

    setWorkspaceId(parseInt(wid))
    loadBots(parseInt(wid))
  }, [router])

  const loadBots = async (wid: number) => {
    try {
      setLoading(true)
      const response = await axios.get(`${API_URL}/ai-bots?workspace_id=${wid}`)
      setBots(response.data)
    } catch (error) {
      console.error('Failed to load bots:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateBot = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceId) return

    try {
      await axios.post(`${API_URL}/ai-bots?workspace_id=${workspaceId}`, {
        name: botName,
        bot_type: 'workspace_default',
        ai_provider: aiProvider,
        ai_model: aiModel,
        system_prompt: systemPrompt,
        auto_respond: true,
        is_active: true
      })

      setBotName('')
      setSystemPrompt('You are a helpful customer support assistant.')
      setShowCreateModal(false)
      loadBots(workspaceId)
    } catch (error) {
      alert('Failed to create bot')
    }
  }

  const handleToggleBot = async (botId: number, currentStatus: boolean) => {
    try {
      await axios.patch(`${API_URL}/ai-bots/${botId}`, {
        is_active: !currentStatus
      })

      setBots(bots.map(bot =>
        bot.id === botId ? { ...bot, is_active: !currentStatus } : bot
      ))
    } catch (error) {
      alert('Failed to toggle bot')
    }
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
          <h1 className="text-2xl font-bold">AI Chatbot Configuration</h1>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Create Bot
          </button>
        </div>

        {/* Create Bot Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4">
              <h2 className="text-xl font-bold mb-4">Create AI Bot</h2>
              <form onSubmit={handleCreateBot} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Bot Name
                  </label>
                  <input
                    type="text"
                    value={botName}
                    onChange={(e) => setBotName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Support Bot"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    AI Provider
                  </label>
                  <select
                    value={aiProvider}
                    onChange={(e) => {
                      setAiProvider(e.target.value)
                      setAiModel(e.target.value === 'openai' ? 'gpt-4' : 'claude-3-opus-20240229')
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    value={aiModel}
                    onChange={(e) => setAiModel(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {aiProvider === 'openai' ? (
                      <>
                        <option value="gpt-4">GPT-4</option>
                        <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                      </>
                    ) : (
                      <>
                        <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                        <option value="claude-3-sonnet-20240229">Claude 3 Sonnet</option>
                      </>
                    )}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    System Prompt
                  </label>
                  <textarea
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={4}
                    placeholder="Define how the AI should behave..."
                    required
                  />
                </div>

                <div className="flex gap-2">
                  <button
                    type="submit"
                    className="flex-1 bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
                  >
                    Create Bot
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

        {/* Bots List */}
        <div className="space-y-4">
          {bots.length === 0 ? (
            <div className="text-center py-12 text-gray-500 bg-white rounded-lg">
              <div className="text-4xl mb-2">🤖</div>
              <p>No AI bots yet. Create one to get started!</p>
            </div>
          ) : (
            bots.map(bot => (
              <div key={bot.id} className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold">{bot.name}</h3>
                      <span className={`px-2 py-1 text-xs rounded-full ${bot.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                        {bot.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600 mb-2">
                      <span className="font-medium">Provider:</span> {bot.ai_provider} ({bot.ai_model})
                    </div>
                    <div className="text-sm text-gray-600">
                      <span className="font-medium">Prompt:</span> {bot.system_prompt}
                    </div>
                  </div>
                  <button
                    onClick={() => handleToggleBot(bot.id, bot.is_active)}
                    className={`px-4 py-2 text-sm rounded-md ${bot.is_active ? 'bg-red-100 text-red-700 hover:bg-red-200' : 'bg-green-100 text-green-700 hover:bg-green-200'}`}
                  >
                    {bot.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
