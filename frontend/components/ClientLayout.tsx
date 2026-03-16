'use client'

import { AuthProvider } from '@/contexts/AuthContext'
import AuthBar from '@/components/AuthBar'
import ApiVersion from '@/components/ApiVersion'

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AuthProvider>
      <AuthBar />
      {children}
      <footer
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          padding: '0.5rem 1rem',
          minHeight: 28,
        }}
        aria-label="API version"
      >
        <ApiVersion />
      </footer>
    </AuthProvider>
  )
}
