'use client'

import { usePathname, useRouter } from 'next/navigation'
import { ReactNode, useState, useEffect } from 'react'

interface DashboardLayoutProps {
  children: ReactNode
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname()
  const router = useRouter()
  const [userId, setUserId] = useState<number | null>(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)

  useEffect(() => {
    const storedUserId = localStorage.getItem('userId')
    if (!storedUserId) {
      router.push('/')
      return
    }
    setUserId(parseInt(storedUserId))
  }, [router])

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', icon: '🏠' },
    { name: 'Messages', path: '/dashboard/messages', icon: '💬' },
    { name: 'Funnels', path: '/funnels', icon: '🎯' },
    { name: 'AI Bots', path: '/dashboard/bots', icon: '🤖' },
  ]

  const handleLogout = () => {
    localStorage.removeItem('userId')
    router.push('/')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside
        className={`${
          isSidebarOpen ? 'w-64' : 'w-20'
        } bg-gradient-to-b from-blue-900 to-blue-800 text-white transition-all duration-300 flex flex-col`}
      >
        {/* Logo */}
        <div className="p-6 border-b border-blue-700">
          <h1 className={`font-bold ${isSidebarOpen ? 'text-2xl' : 'text-xl text-center'}`}>
            {isSidebarOpen ? '🚀 Social CRM' : '🚀'}
          </h1>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => {
            const isActive = pathname === item.path
            return (
              <button
                key={item.path}
                onClick={() => router.push(item.path)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                  isActive
                    ? 'bg-blue-700 text-white shadow-lg'
                    : 'hover:bg-blue-800 text-blue-100'
                }`}
              >
                <span className="text-xl">{item.icon}</span>
                {isSidebarOpen && <span className="font-medium">{item.name}</span>}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-blue-700 space-y-2">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="w-full px-4 py-2 bg-blue-800 hover:bg-blue-700 rounded-lg transition-colors text-sm"
          >
            {isSidebarOpen ? '←' : '→'}
          </button>
          {isSidebarOpen && (
            <button
              onClick={handleLogout}
              className="w-full px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors text-sm font-medium"
            >
              Logout
            </button>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {/* Top Bar */}
        <header className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {navItems.find((item) => item.path === pathname)?.name || 'Dashboard'}
              </h2>
              <p className="text-sm text-gray-500">Manage your social messaging</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="px-4 py-2 bg-blue-50 rounded-lg">
                <span className="text-sm text-blue-900 font-medium">User #{userId}</span>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="p-6">{children}</div>
      </main>
    </div>
  )
}
