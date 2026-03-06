'use client'

import { AuthProvider } from '@/contexts/AuthContext'
import AuthBar from '@/components/AuthBar'

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AuthProvider>
      <AuthBar />
      {children}
    </AuthProvider>
  )
}
