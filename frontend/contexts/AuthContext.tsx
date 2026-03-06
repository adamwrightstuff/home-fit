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
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const client = createClient()
  const isConfigured = client !== null

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
      const { error } = await client.auth.signUp({ email, password })
      return { error: error ?? null }
    },
    [client]
  )

  const signOut = useCallback(async () => {
    if (client) await client.auth.signOut()
  }, [client])

  const value: AuthContextValue = {
    user,
    session,
    loading,
    isConfigured: isConfigured ?? false,
    signIn,
    signUp,
    signOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
