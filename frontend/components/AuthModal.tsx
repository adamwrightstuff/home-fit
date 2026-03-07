'use client'

import React, { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'

type Mode = 'signin' | 'signup'

export default function AuthModal({
  isOpen,
  onClose,
  initialMode = 'signin',
}: {
  isOpen: boolean
  onClose: () => void
  initialMode?: Mode
}) {
  const { signIn, signUp, resendConfirmation, isConfigured } = useAuth()
  const [mode, setMode] = useState<Mode>(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState<string | null>(null)
  const [resendSent, setResendSent] = useState(false)

  // When modal opens or initialMode changes, show the correct tab (Sign in vs Sign up)
  useEffect(() => {
    if (isOpen) {
      setMode(initialMode)
      setResendSent(false)
    }
  }, [isOpen, initialMode])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) {
      setError('Email is required')
      return
    }
    if (!password && mode === 'signin') {
      setError('Password is required')
      return
    }
    if (mode === 'signup' && password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }
    setError(null)
    setSuccess(null)
    setSubmitting(true)
    try {
      if (mode === 'signin') {
        const { error: err } = await signIn(email.trim(), password)
        if (err) {
          setError(err.message)
          return
        }
        onClose()
      } else {
        const { error: err } = await signUp(email.trim(), password)
        if (err) {
          setError(err.message)
          return
        }
        setSuccess('Check your email to confirm your account.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleResend = async () => {
    if (!email.trim()) return
    setError(null)
    setResendSent(false)
    const { error: err } = await resendConfirmation(email.trim())
    if (err) {
      setError(err.message)
      return
    }
    setResendSent(true)
  }

  if (!isOpen) return null
  if (!isConfigured) {
    return (
      <div
        className="hf-auth-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title"
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <div className="hf-auth-modal">
          <div className="hf-auth-modal-header">
            <h2 id="auth-modal-title">Sign in</h2>
            <button
              type="button"
              className="hf-auth-close"
              onClick={onClose}
              aria-label="Close"
            >
              ×
            </button>
          </div>
          <p className="hf-auth-success">
            Auth is not configured. Add <code>NEXT_PUBLIC_SUPABASE_URL</code> and{' '}
            <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> to your deployment environment (e.g. Vercel project settings), then redeploy.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="hf-auth-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="hf-auth-modal">
        <div className="hf-auth-modal-header">
          <h2 id="auth-modal-title">{mode === 'signin' ? 'Sign in' : 'Create account'}</h2>
          <button
            type="button"
            className="hf-auth-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="hf-auth-field">
            <label htmlFor="auth-email">Email</label>
            <input
              id="auth-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={submitting}
            />
          </div>
          <div className="hf-auth-field">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === 'signup' ? 'At least 6 characters' : ''}
              disabled={submitting}
            />
          </div>
          {error && (
            <p className="hf-auth-error" role="alert">
              {error}
            </p>
          )}
          {success && (
            <p className="hf-auth-success" role="status">
              {success}
              {mode === 'signup' && (
                <>
                  {' '}
                  Didn&apos;t get it?{' '}
                  <button
                    type="button"
                    className="hf-auth-link"
                    onClick={handleResend}
                    disabled={submitting}
                  >
                    Resend email
                  </button>
                </>
              )}
            </p>
          )}
          {resendSent && (
            <p className="hf-auth-success" role="status">
              Confirmation email sent again. Check your inbox.
            </p>
          )}
          <div className="hf-auth-actions">
            <button type="submit" className="hf-auth-submit" disabled={submitting}>
              {submitting ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Sign up'}
            </button>
          </div>
          {mode === 'signin' && email.trim() && (
            <p className="hf-auth-switch" style={{ marginTop: '0.75rem' }}>
              Waiting for confirmation email?{' '}
              <button type="button" className="hf-auth-link" onClick={handleResend} disabled={submitting}>
                Resend
              </button>
            </p>
          )}
        </form>
        <p className="hf-auth-switch">
          {mode === 'signin' ? (
            <>
              Don&apos;t have an account?{' '}
              <button type="button" className="hf-auth-link" onClick={() => { setMode('signup'); setError(null); setSuccess(null); }}>
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button type="button" className="hf-auth-link" onClick={() => { setMode('signin'); setError(null); setSuccess(null); }}>
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
