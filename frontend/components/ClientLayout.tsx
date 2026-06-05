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
      <div style={{ overflowX: 'clip', maxWidth: '100%', isolation: 'isolate' }}>
      <AuthBar />
      {children}
      <footer
        className="hf-api-version-footer"
        aria-label="API version"
      >
        <ApiVersion />
      </footer>
      </div>
    </AuthProvider>
  )
}
