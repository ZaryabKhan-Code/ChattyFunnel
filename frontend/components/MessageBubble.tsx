import { formatDistanceToNow } from 'date-fns'
import type { Message } from '@/lib/api'

const API_URL = 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'

interface MessageBubbleProps {
  message: Message
  userId?: number | null
}

export default function MessageBubble({ message, userId }: MessageBubbleProps) {
  const isOutgoing = message.direction === 'outgoing'

  // Construct proxy URL for attachments to avoid 403 errors
  const getMediaUrl = () => {
    if (!message.attachment_url || !userId) return message.attachment_url
    return `${API_URL}/media/attachment/${message.message_id}?user_id=${userId}`
  }

  const mediaUrl = getMediaUrl()

  const renderAttachment = () => {
    if (!mediaUrl) return null

    switch (message.message_type) {
      case 'image':
        return (
          <a href={mediaUrl} target="_blank" rel="noopener noreferrer">
            <img
              src={mediaUrl}
              alt="Image attachment"
              className="max-w-full rounded-lg mb-2 cursor-pointer hover:opacity-90"
              onError={(e) => {
                // Fallback to original URL if proxy fails
                const img = e.target as HTMLImageElement
                if (img.src !== message.attachment_url) {
                  img.src = message.attachment_url || ''
                }
              }}
            />
          </a>
        )
      case 'video':
        return (
          <video
            src={mediaUrl}
            controls
            className="max-w-full rounded-lg mb-2"
            onError={(e) => {
              // Fallback to original URL if proxy fails
              const video = e.target as HTMLVideoElement
              if (video.src !== message.attachment_url) {
                video.src = message.attachment_url || ''
              }
            }}
          />
        )
      case 'audio':
        return (
          <audio
            src={mediaUrl}
            controls
            className="mb-2 w-full"
            onError={(e) => {
              // Fallback to original URL if proxy fails
              const audio = e.target as HTMLAudioElement
              if (audio.src !== message.attachment_url) {
                audio.src = message.attachment_url || ''
              }
            }}
          />
        )
      case 'file':
        return (
          <a
            href={mediaUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={`flex items-center gap-2 p-2 rounded mb-2 ${
              isOutgoing ? 'bg-blue-700' : 'bg-gray-300'
            }`}
          >
            <span className="text-2xl">📎</span>
            <span className="text-sm">{message.attachment_filename || 'Download file'}</span>
          </a>
        )
      default:
        return null
    }
  }

  return (
    <div className={`flex ${isOutgoing ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
          isOutgoing
            ? 'bg-blue-600 text-white rounded-br-none'
            : 'bg-gray-200 text-gray-800 rounded-bl-none'
        }`}
      >
        {renderAttachment()}
        {message.content && <p className="break-words">{message.content}</p>}
        <div className="flex items-center justify-between gap-2 mt-1">
          <p
            className={`text-xs ${
              isOutgoing ? 'text-blue-100' : 'text-gray-600'
            }`}
          >
            {formatDistanceToNow(new Date(message.created_at), {
              addSuffix: true,
            })}
          </p>
          {isOutgoing && (
            <span
              className={`text-xs ${
                message.status === 'sent'
                  ? 'text-blue-200'
                  : message.status === 'delivered'
                  ? 'text-blue-100'
                  : message.status === 'read'
                  ? 'text-green-300'
                  : 'text-red-300'
              }`}
            >
              {message.status === 'sent' && '✓'}
              {message.status === 'delivered' && '✓✓'}
              {message.status === 'read' && '✓✓'}
              {message.status === 'failed' && '✗'}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
