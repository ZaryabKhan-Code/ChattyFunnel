import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { WorkspaceProvider } from '@/contexts/WorkspaceContext'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Social Messaging Integration',
  description: 'Connect Facebook and Instagram accounts to manage messages',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // TODO: Replace with actual user ID from auth system
  const userId = 1

  return (
    <html lang="en">
      <body className={inter.className}>
        <WorkspaceProvider userId={userId}>
          {children}
        </WorkspaceProvider>
      </body>
    </html>
  )
}
