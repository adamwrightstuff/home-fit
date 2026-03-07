'use client'

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { createClient } from '@/lib/supabase/client'

interface AuthContextValue {
  user: User | null
  session: Session | null
  loading: boolean
  isConfigured: boolean
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>
  signUp: (email: string, password: string) => Promise<{ error: Error | null }>
  resendConfirmation: (email: string) => Promise<{ error: Error | null }>
  resetPasswordForEmail: (email: string) => Promise<{ error: Error | null }>
  signOut: () => Promise<void>
  /** Open the auth modal (sign-in or sign-up). Call from anywhere (e.g. "Sign in to save this place"). */
  openAuthModal: (mode?: 'signin' | 'signup') => void
  closeAuthModal: () => void
  authModalOpen: boolean
  authModalMode: 'signin' | 'signup'
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authModalMode, setAuthModalMode] = useState<'signin' | 'signup'>('signin')
  const client = createClient()
  const isConfigured = client !== null

  const openAuthModal = useCallback((mode: 'signin' | 'signup' = 'signin') => {
    setAuthModalMode(mode)
    setAuthModalOpen(true)
  }, [])
  const closeAuthModal = useCallback(() => setAuthModalOpen(false), [])

  useEffect(() => {
    if (!client) {
      setLoading(false)
      return
    }
    client.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })
    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
    })
    return () => subscription.unsubscribe()
  }, [client])

  const signIn = useCallback(
    async (email: string, password: string) => {
      if (!client) return { error: new Error('Auth not configured') }
      const { error } = await client.auth.signInWithPassword({ email, password })
      return { error: error ?? null }
    },
    [client]
  )

  const signUp = useCallback(
    async (email: string, password: string) => {
      if (!client) return { error: new Error('Auth not configured') }
      const emailRedirectTo =
        typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : undefined
      const { error } = await client.auth.signUp({
        email,
        password,
        options: emailRedirectTo ? { emailRedirectTo } : undefined,
      })
      return { error: error ?? null }
    },
    [client]
  )

  const signOut = useCallback(async () => {
    if (client) await client.auth.signOut()
  }, [client])

  const resendConfirmation = useCallback(
    async (email: string) => {
      if (!client) return { error: new Error('Auth not configured') }
      const { error } = await client.auth.resend({
        type: 'signup',
        email: email.trim(),
      })
      return { error: error ?? null }
    },
    [client]
  )

  const resetPasswordForEmail = useCallback(
    async (email: string) => {
      if (!client) return { error: new Error('Auth not configured') }
      const redirectTo =
        typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : undefined
      const { error } = await client.auth.resetPasswordForEmail(email.trim(), {
        redirectTo,
      })
      return { error: error ?? null }
    },
    [client]
  )

  const value: AuthContextValue = {
    user,
    session,
    loading,
    isConfigured: isConfigured ?? false,
    signIn,
    signUp,
    resendConfirmation,
    resetPasswordForEmail,
    signOut,
    openAuthModal,
    closeAuthModal,
    authModalOpen,
    authModalMode,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
