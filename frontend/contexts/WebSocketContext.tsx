'use client'

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react'

interface WebSocketMessage {
  type: string
  data: any
}

type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'

interface WebSocketContextType {
  isConnected: boolean
  connectionState: ConnectionState
  lastMessage: WebSocketMessage | null
  lastError: string | null
  sendMessage: (message: string) => void
  connect: () => void
  disconnect: () => void
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState<number | null>(null)
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
  const isConnecting = useRef(false)

  // Get WebSocket URL
  const getWebSocketUrl = useCallback((uid: number) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://roamifly-admin-b97e90c67026.herokuapp.com/api'
    const wsProtocol = apiUrl.includes('https') ? 'wss' : 'ws'
    const wsHost = apiUrl.replace('https://', '').replace('http://', '').replace('/api/v1', '').replace('/api', '')
    return `${wsProtocol}://${wsHost}/api/ws/${uid}`
  }, [])

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

  // Cleanup function for intervals and timeouts
  const cleanup = useCallback(() => {
    if (pingInterval.current) {
      clearInterval(pingInterval.current)
      pingInterval.current = null
    }
    if (pongTimeout.current) {
      clearTimeout(pongTimeout.current)
      pongTimeout.current = null
    }
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current)
      reconnectTimeout.current = null
    }
  }, [])

  // Connect function
  const connectWebSocket = useCallback((uid: number) => {
    // Prevent duplicate connections
    if (isConnecting.current) {
      console.log('⚠️ Already connecting, skipping...')
      return
    }

    // Don't reconnect if manually closed
    if (isManualClose.current) {
      console.log('⚠️ Manual close - not reconnecting')
      return
    }

    // Check if already connected
    if (ws.current?.readyState === WebSocket.OPEN) {
      console.log('✅ Already connected, skipping...')
      return
    }

    // Check if currently connecting
    if (ws.current?.readyState === WebSocket.CONNECTING) {
      console.log('⏳ Connection in progress, skipping...')
      return
    }

    const wsUrl = getWebSocketUrl(uid)
    isConnecting.current = true
    console.log('🔌 Connecting to WebSocket:', wsUrl)
    setConnectionState('connecting')
    setLastError(null)

    // Clean up existing connection
    cleanup()
    if (ws.current) {
      ws.current.onclose = null
      ws.current.onerror = null
      ws.current.onmessage = null
      ws.current.onopen = null
      ws.current.close()
      ws.current = null
    }

    try {
      ws.current = new WebSocket(wsUrl)

      ws.current.onopen = () => {
        console.log('✅ WebSocket connected successfully')
        isConnecting.current = false
        setIsConnected(true)
        setConnectionState('connected')
        setLastError(null)
        reconnectAttempts.current = 0

        // Flush any queued messages
        flushMessageQueue()

        // Send ping every 15 seconds to keep connection alive
        pingInterval.current = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send('ping')

            // Set timeout to detect if pong is not received
            pongTimeout.current = setTimeout(() => {
              console.error('❌ Pong not received! Reconnecting...')
              setIsConnected(false)
              setConnectionState('error')
              setLastError('Heartbeat timeout')
              if (ws.current) {
                ws.current.close()
              }
            }, 5000)
          }
        }, 15000)
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          // Handle pong response
          if (data.type === 'pong') {
            if (pongTimeout.current) {
              clearTimeout(pongTimeout.current)
              pongTimeout.current = null
            }
            return
          }

          // Update last message for all other message types
          console.log('🔔 WebSocket message:', data.type, data.data)
          setLastMessage(data)
        } catch (error) {
          console.error('❌ Failed to parse WebSocket message:', error)
        }
      }

      ws.current.onerror = (error) => {
        console.error('❌ WebSocket error')
        isConnecting.current = false
        setIsConnected(false)
        setConnectionState('error')
        setLastError('WebSocket connection error')
      }

      ws.current.onclose = (event) => {
        console.log('🔌 WebSocket disconnected', { code: event.code, wasClean: event.wasClean })
        isConnecting.current = false
        setIsConnected(false)
        setConnectionState('disconnected')
        cleanup()

        // Don't reconnect if manually closed or user not found
        if (isManualClose.current || event.code === 1008) {
          return
        }

        // Attempt to reconnect with exponential backoff
        const delay = reconnectAttempts.current === 0 ? 500 : Math.min(1000 * Math.pow(2, reconnectAttempts.current - 1), 10000)
        reconnectAttempts.current++

        console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})...`)
        setLastError(`Reconnecting... (attempt ${reconnectAttempts.current})`)

        reconnectTimeout.current = setTimeout(() => connectWebSocket(uid), delay)
      }
    } catch (error) {
      console.error('❌ Failed to create WebSocket:', error)
      isConnecting.current = false
      setConnectionState('error')
      setLastError('Failed to create connection')
    }
  }, [getWebSocketUrl, flushMessageQueue, cleanup])

  // Disconnect function - call this on logout
  const disconnect = useCallback(() => {
    console.log('🔌 Disconnecting WebSocket (manual)')
    isManualClose.current = true
    cleanup()
    if (ws.current) {
      ws.current.onclose = null // Prevent reconnection
      ws.current.close()
      ws.current = null
    }
    setIsConnected(false)
    setConnectionState('disconnected')
    setUserId(null)
  }, [cleanup])

  // Manual connect function - call this on login
  const connect = useCallback(() => {
    const storedUserId = localStorage.getItem('userId')
    if (storedUserId) {
      const uid = parseInt(storedUserId)
      setUserId(uid)
      isManualClose.current = false
      reconnectAttempts.current = 0
      connectWebSocket(uid)
    }
  }, [connectWebSocket])

  // Check for userId changes (login/logout)
  useEffect(() => {
    // Check for existing login on mount
    const checkAuth = () => {
      const storedUserId = localStorage.getItem('userId')
      if (storedUserId && !userId) {
        const uid = parseInt(storedUserId)
        setUserId(uid)
        isManualClose.current = false
        // Small delay for React StrictMode
        setTimeout(() => connectWebSocket(uid), 100)
      } else if (!storedUserId && userId) {
        // User logged out
        disconnect()
      }
    }

    checkAuth()

    // Listen for storage changes (login/logout in other tabs)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'userId') {
        if (e.newValue) {
          const uid = parseInt(e.newValue)
          setUserId(uid)
          isManualClose.current = false
          connectWebSocket(uid)
        } else {
          disconnect()
        }
      }
    }

    window.addEventListener('storage', handleStorageChange)

    // Monitor online/offline status
    const handleOnline = () => {
      console.log('🌐 Network is online')
      if (userId && !isConnected && !isConnecting.current) {
        reconnectAttempts.current = 0
        connectWebSocket(userId)
      }
    }

    const handleOffline = () => {
      console.log('📡 Network is offline')
      setConnectionState('disconnected')
      setLastError('Network offline')
    }

    // Reconnect when tab becomes visible (with debounce)
    let visibilityTimeout: NodeJS.Timeout | null = null
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && userId) {
        if (visibilityTimeout) clearTimeout(visibilityTimeout)
        visibilityTimeout = setTimeout(() => {
          if (ws.current?.readyState !== WebSocket.OPEN && !isConnecting.current && !isManualClose.current) {
            console.log('👁️ Tab visible - reconnecting')
            reconnectAttempts.current = 0
            connectWebSocket(userId)
          }
        }, 500)
      }
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      if (visibilityTimeout) clearTimeout(visibilityTimeout)
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [userId, isConnected, connectWebSocket, disconnect])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup()
      if (ws.current) {
        ws.current.close()
        ws.current = null
      }
    }
  }, [cleanup])

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        connectionState,
        lastMessage,
        lastError,
        sendMessage,
        connect,
        disconnect
      }}
    >
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext)
  if (context === undefined) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider')
  }
  return context
}
