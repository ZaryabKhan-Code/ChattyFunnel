import { formatDistanceToNow } from 'date-fns'
import type { Conversation } from '@/lib/api'

const API_URL = 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

// Helper to proxy profile pictures through backend to avoid CORS/403 errors
const getProxiedProfilePic = (url: string | null) => {
  if (!url) return null
  return `${API_URL}/media/profile-pic?url=${encodeURIComponent(url)}`
}

interface ConversationItemProps {
  conversation: Conversation
  isSelected: boolean
  onClick: () => void
  onAIToggle?: (conversationId: string, enabled: boolean) => void
}

export default function ConversationItem({
  conversation,
  isSelected,
  onClick,
  onAIToggle,
}: ConversationItemProps) {

  const handleAIToggle = (e: React.MouseEvent) => {
    e.stopPropagation() // Prevent conversation selection when clicking AI toggle
    if (onAIToggle) {
      onAIToggle(conversation.conversation_id, !conversation.ai_enabled)
    }
  }
  const getMessagePreview = () => {
    if (!conversation.last_message) return ''

    if (conversation.last_message.content) {
      return conversation.last_message.content
    }

    // Show media type if no text content
    switch (conversation.last_message.message_type) {
      case 'image':
        return '📷 Photo'
      case 'video':
        return '🎥 Video'
      case 'audio':
        return '🎵 Voice message'
      case 'file':
        return '📎 File'
      default:
        return 'Message'
    }
  }

  return (
    <div
      onClick={onClick}
      className={`p-3 rounded-lg cursor-pointer transition-all ${
        isSelected
          ? 'bg-blue-50 border border-blue-200 shadow-sm'
          : 'hover:bg-gray-50 border border-transparent'
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Profile Picture */}
        <div className="flex-shrink-0">
          {conversation.participant_profile_pic ? (
            <img
              src={getProxiedProfilePic(conversation.participant_profile_pic) || ''}
              alt={conversation.participant_name || 'User'}
              className="w-12 h-12 rounded-full object-cover"
              onError={(e) => {
                // Fallback to initials if image fails to load
                const target = e.target as HTMLImageElement
                target.style.display = 'none'
              }}
            />
          ) : (
            <div className="w-12 h-12 rounded-full bg-gray-300 flex items-center justify-center text-gray-600 font-semibold">
              {(conversation.participant_name || conversation.participant_id)[0].toUpperCase()}
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <p className="font-semibold text-gray-800 truncate">
              {conversation.participant_name || conversation.participant_username || conversation.participant_id}
            </p>
            <div className="flex items-center gap-1">
              {conversation.unread_count > 0 && (
                <span className="bg-blue-600 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                  {conversation.unread_count}
                </span>
              )}
              <button
                onClick={handleAIToggle}
                className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
                  conversation.ai_enabled
                    ? 'bg-green-100 text-green-700 hover:bg-green-200'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
                title={conversation.ai_enabled ? 'AI Auto-response: ON' : 'AI Auto-response: OFF'}
              >
                🤖 {conversation.ai_enabled ? 'ON' : 'OFF'}
              </button>
            </div>
          </div>
          {conversation.last_message && (
            <>
              <p className="text-sm text-gray-600 truncate mb-1">
                {conversation.last_message.direction === 'outgoing' && (
                  <span className="text-blue-600 mr-1">You:</span>
                )}
                {getMessagePreview()}
              </p>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400 capitalize">
                  {conversation.platform}
                </span>
                <span className="text-xs text-gray-400">•</span>
                <span className="text-xs text-gray-400">
                  {formatDistanceToNow(new Date(conversation.last_message.created_at), {
                    addSuffix: true,
                  })}
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
