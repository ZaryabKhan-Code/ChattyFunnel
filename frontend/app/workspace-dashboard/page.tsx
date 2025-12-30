'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function WorkspaceDashboard() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to main dashboard
    router.push('/dashboard')
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="text-6xl mb-4">🔄</div>
        <p className="text-gray-600">Redirecting to dashboard...</p>
      </div>
    </div>
  )
}
