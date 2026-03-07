'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

/**
 * Auth callback: Supabase redirects here after email confirmation (and similar flows)
 * with tokens in the URL hash. We exchange them for a session and redirect home.
 */
export default function AuthCallbackPage() {
  const router = useRouter()
  const [status, setStatus] = useState<'Completing sign in…' | 'Redirecting…' | 'Something went wrong.'>('Completing sign in…')

  useEffect(() => {
    const client = createClient()
    if (!client) {
      setStatus('Something went wrong.')
      return
    }

    const hash = typeof window !== 'undefined' ? window.location.hash : ''
    const params = new URLSearchParams(hash.replace(/^#/, ''))

    const access_token = params.get('access_token')
    const refresh_token = params.get('refresh_token')
    const error = params.get('error_description') || params.get('error')

    if (error) {
      console.error('Auth callback error:', error)
      setStatus('Something went wrong.')
      return
    }

    if (access_token && refresh_token) {
      setStatus('Redirecting…')
      client.auth
        .setSession({ access_token, refresh_token })
        .then(() => {
          router.replace('/')
        })
        .catch((err) => {
          console.error('setSession error:', err)
          setStatus('Something went wrong.')
        })
      return
    }

    // No tokens in URL (e.g. user opened /auth/callback by mistake)
    router.replace('/')
  }, [router])

  return (
    <div className="hf-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <p className="hf-muted" style={{ fontSize: '1.1rem' }}>{status}</p>
    </div>
  )
}
