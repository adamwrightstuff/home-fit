'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'

export default function UpdatePasswordPage() {
  const router = useRouter()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setError(null)
    setSubmitting(true)
    const client = createClient()
    if (!client) {
      setError('Auth not configured')
      setSubmitting(false)
      return
    }
    const { error: err } = await client.auth.updateUser({ password })
    setSubmitting(false)
    if (err) {
      setError(err.message)
      return
    }
    setDone(true)
    setTimeout(() => router.replace('/'), 1500)
  }

  if (done) {
    return (
      <div className="hf-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', flexDirection: 'column', gap: '1rem' }}>
        <p className="hf-auth-success">Password updated. Redirecting…</p>
        <Link href="/" className="hf-auth-link">Go home</Link>
      </div>
    )
  }

  return (
    <div className="hf-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <div className="hf-auth-modal" style={{ maxWidth: '400px' }}>
        <h2 style={{ margin: '0 0 1.5rem', fontSize: '1.5rem', fontWeight: 700 }}>Set new password</h2>
        <form onSubmit={handleSubmit}>
          <div className="hf-auth-field">
            <label htmlFor="new-password">New password</label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              disabled={submitting}
            />
          </div>
          <div className="hf-auth-field">
            <label htmlFor="confirm-password">Confirm password</label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              disabled={submitting}
            />
          </div>
          {error && (
            <p className="hf-auth-error" role="alert">{error}</p>
          )}
          <div className="hf-auth-actions">
            <button type="submit" className="hf-auth-submit" disabled={submitting}>
              {submitting ? 'Updating…' : 'Update password'}
            </button>
          </div>
        </form>
        <p className="hf-auth-switch" style={{ marginTop: '1rem' }}>
          <Link href="/" className="hf-auth-link">Back to home</Link>
        </p>
      </div>
    </div>
  )
}
