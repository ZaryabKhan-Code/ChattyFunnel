import { useEffect, useRef, useState, useCallback } from 'react'

interface WebSocketMessage {
  type: string
  data: any
}

type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'

export function useWebSocket(userId: number | null) {
  const [isConnected, setIsConnected] = useState(false)
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)

  const ws = useRef<WebSocket | null>(null)
  const pingInterval = useRef<NodeJS.Timeout | null>(null)
  const pongTimeout = useRef<NodeJS.Timeout | null>(null)
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)
  const messageQueue = useRef<string[]>([])
  const isManualClose = useRef(false)

  const connect = useRef<(() => void) | null>(null)

  // Get WebSocket URL - Updated to use /api/v1/ws/
  const getWebSocketUrl = useCallback(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'
    const wsProtocol = apiUrl.includes('https') ? 'wss' : 'ws'
    const wsHost = apiUrl.replace('https://', '').replace('http://', '').replace('/api/v1', '').replace('/api', '')
    return `${wsProtocol}://${wsHost}/api/ws/${userId}`
  }, [userId])

  // Send message with queuing for offline support
  const sendMessage = useCallback((message: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(message)
      console.log('📤 Message sent:', message)
    } else {
      console.log('📦 Message queued (WebSocket not connected):', message)
      messageQueue.current.push(message)
    }
  }, [])

  // Flush queued messages when connection is established
  const flushMessageQueue = useCallback(() => {
    if (messageQueue.current.length > 0 && ws.current?.readyState === WebSocket.OPEN) {
      console.log(`📦 Flushing ${messageQueue.current.length} queued messages`)
      while (messageQueue.current.length > 0) {
        const message = messageQueue.current.shift()
        if (message) {
          ws.current.send(message)
        }
      }
    }
  }, [])

  useEffect(() => {
    if (!userId) return

    const wsUrl = getWebSocketUrl()

    connect.current = () => {
      // Don't reconnect if manually closed
      if (isManualClose.current) {
        console.log('⚠️ Manual close - not reconnecting')
        return
      }

      console.log('🔌 Connecting to WebSocket:', wsUrl)
      setConnectionState('connecting')
      setLastError(null)

      // Clean up existing connection if any
      if (ws.current) {
        ws.current.close()
      }

      try {
        // Connect to WebSocket
        ws.current = new WebSocket(wsUrl)

        if (!ws.current) {
          throw new Error('Failed to create WebSocket instance')
        }

        ws.current.onopen = () => {
          console.log('✅ WebSocket connected successfully')
          setIsConnected(true)
          setConnectionState('connected')
          setLastError(null)
          reconnectAttempts.current = 0

          // Flush any queued messages
          flushMessageQueue()

          // Send ping every 15 seconds to keep connection alive
          pingInterval.current = setInterval(() => {
            if (ws.current?.readyState === WebSocket.OPEN) {
              console.log('🏓 Sending ping...')
              ws.current.send('ping')

              // Set timeout to detect if pong is not received
              pongTimeout.current = setTimeout(() => {
                console.error('❌ Pong not received! Connection appears dead. Reconnecting...')
                setIsConnected(false)
                setConnectionState('error')
                setLastError('Heartbeat timeout')
                if (ws.current) {
                  ws.current.close()
                }
                // Reconnect will happen in onclose
              }, 5000) // Wait 5 seconds for pong
            }
          }, 15000) // Ping every 15 seconds
        }
      } catch (error) {
        console.error('❌ Failed to create WebSocket:', error)
        setConnectionState('error')
        setLastError('Failed to create connection')
      }

      if (ws.current) {
        ws.current.onmessage = (event) => {
          try {
            console.log('🔔 Raw WebSocket message received:', event.data)
            const data = JSON.parse(event.data)
            console.log('🔔 Parsed WebSocket message:', data)
            console.log('🔔 Message type:', data.type)

            // Handle pong response
            if (data.type === 'pong') {
              console.log('✅ Pong received - connection alive')
              // Clear the pong timeout since we received response
              if (pongTimeout.current) {
                clearTimeout(pongTimeout.current)
                pongTimeout.current = null
              }
              return
            }

            // Update last message for all other message types
            console.log('🔔 Message data:', data.data)
            setLastMessage(data)
          } catch (error) {
            console.error('❌ Failed to parse WebSocket message:', error, event.data)
            // Still try to set message even if parsing fails
            setLastMessage({
              type: 'error',
              data: { error: 'Failed to parse message', raw: event.data }
            })
          }
        }

        ws.current.onerror = (error) => {
          console.error('❌ WebSocket error:', error)
          setIsConnected(false)
          setConnectionState('error')
          setLastError('WebSocket connection error')
        }

        ws.current.onclose = (event) => {
          console.log('🔌 WebSocket disconnected', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean
          })
          setIsConnected(false)
          setConnectionState('disconnected')

          // Clear intervals and timeouts
          if (pingInterval.current) {
            clearInterval(pingInterval.current)
            pingInterval.current = null
          }
          if (pongTimeout.current) {
            clearTimeout(pongTimeout.current)
            pongTimeout.current = null
          }

          // Don't reconnect if it was a manual close or user not found (code 1008)
          if (isManualClose.current || event.code === 1008) {
            console.log('❌ Not reconnecting:', {
              manual: isManualClose.current,
              userNotFound: event.code === 1008
            })
            setLastError(event.code === 1008 ? 'User not found' : 'Connection closed')
            return
          }

          // Attempt to reconnect with exponential backoff
          // Start immediately, then 1s, 2s, 4s, max 10 seconds
          const delay = reconnectAttempts.current === 0 ? 100 : Math.min(1000 * Math.pow(2, reconnectAttempts.current - 1), 10000)
          reconnectAttempts.current++

          console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})...`)
          setLastError(`Reconnecting in ${Math.round(delay / 1000)}s (attempt ${reconnectAttempts.current})`)

          reconnectTimeout.current = setTimeout(() => {
            if (connect.current) {
              connect.current()
            }
          }, delay)
        }
      }
    }

    // Initial connection
    connect.current?.()

    // Monitor online/offline status
    const handleOnline = () => {
      console.log('🌐 Network is online - reconnecting WebSocket')
      if (!isConnected && connect.current) {
        reconnectAttempts.current = 0 // Reset attempts when network comes back
        connect.current()
      }
    }

    const handleOffline = () => {
      console.log('📡 Network is offline - WebSocket will reconnect when online')
      setConnectionState('disconnected')
      setLastError('Network offline')
    }

    // Reconnect when tab becomes visible
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('👁️ Tab became visible - checking WebSocket connection')
        if (ws.current?.readyState !== WebSocket.OPEN && connect.current && !isManualClose.current) {
          console.log('🔄 WebSocket not open, reconnecting...')
          reconnectAttempts.current = 0
          connect.current()
        }
      }
    }

    // Focus handler for immediate reconnection
    const handleFocus = () => {
      console.log('🎯 Window focused - checking WebSocket connection')
      if (ws.current?.readyState !== WebSocket.OPEN && connect.current && !isManualClose.current) {
        console.log('🔄 WebSocket not open, reconnecting...')
        reconnectAttempts.current = 0
        connect.current()
      }
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('focus', handleFocus)

    // Cleanup
    return () => {
      isManualClose.current = true

      if (ws.current) {
        ws.current.close()
      }
      if (pingInterval.current) {
        clearInterval(pingInterval.current)
      }
      if (pongTimeout.current) {
        clearTimeout(pongTimeout.current)
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current)
      }

      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', handleFocus)
    }
  }, [userId, getWebSocketUrl, flushMessageQueue])

  // Manual disconnect function
  const disconnect = useCallback(() => {
    isManualClose.current = true
    if (ws.current) {
      ws.current.close()
    }
    setIsConnected(false)
    setConnectionState('disconnected')
  }, [])

  // Manual reconnect function
  const reconnect = useCallback(() => {
    isManualClose.current = false
    reconnectAttempts.current = 0
    if (connect.current) {
      connect.current()
    }
  }, [])

  return {
    isConnected,
    connectionState,
    lastMessage,
    lastError,
    sendMessage,
    disconnect,
    reconnect
  }
}
