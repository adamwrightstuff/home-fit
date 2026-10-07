'use client'

import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { fetchProfile, readLocalProfile, type UserProfile } from '@/lib/userProfile'

/**
 * The viewer's personal profile: local explorer settings first, overridden by the saved account
 * profile once it loads for a signed-in user. Empty object until something is known.
 */
export function useProfile(): Partial<UserProfile> {
  const { user } = useAuth()
  const [local, setLocal] = useState<Partial<UserProfile>>({})
  const [remote, setRemote] = useState<Partial<UserProfile> | null>(null)

  useEffect(() => { setLocal(readLocalProfile()) }, [])

  useEffect(() => {
    if (!user) { setRemote(null); return }
    let cancelled = false
    fetchProfile().then((p) => { if (!cancelled) setRemote(p) })
    return () => { cancelled = true }
  }, [user])

  return useMemo(() => ({ ...local, ...(remote ?? {}) }), [local, remote])
}
