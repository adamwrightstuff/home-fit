import { loadPeople, type SocialConnectionPerson } from '@/lib/socialConnections'

export type CommuteMode = 'auto' | 'transit' | 'active'

/** Personal facts that adjust cached place scores. Stored in user_preferences.profile. */
export interface UserProfile {
  household_income: number | null
  current_home: { name: string; monthly_cost: number | null } | null
  work_zone_id: string | null
  commute_mode: CommuteMode | null
  /** Days per week in the office, 0 (fully remote) to 5. */
  office_days: number | null
  people: SocialConnectionPerson[]
}

const MODES: CommuteMode[] = ['auto', 'transit', 'active']

function isPerson(p: any): p is SocialConnectionPerson {
  return (
    p && typeof p.id === 'string' && typeof p.lat === 'number' && typeof p.lon === 'number' &&
    (p.tier === 'close' || p.tier === 'acquaintance')
  )
}

/**
 * Validates untrusted profile JSON. Only keys that are present and valid come back, so callers
 * can merge a partial profile without wiping fields they don't know about; null clears a
 * nullable field.
 */
export function sanitizeProfile(raw: unknown): Partial<UserProfile> {
  const out: Partial<UserProfile> = {}
  if (!raw || typeof raw !== 'object') return out
  const r = raw as Record<string, unknown>

  if ('household_income' in r) {
    const v = r.household_income
    if (v === null) out.household_income = null
    else if (typeof v === 'number' && Number.isFinite(v) && v > 0) out.household_income = v
  }
  if ('current_home' in r) {
    const v = r.current_home as any
    if (v === null) out.current_home = null
    else if (v && typeof v.name === 'string' && v.name) {
      const cost = typeof v.monthly_cost === 'number' && Number.isFinite(v.monthly_cost) && v.monthly_cost > 0
        ? v.monthly_cost : null
      out.current_home = { name: v.name, monthly_cost: cost }
    }
  }
  if ('work_zone_id' in r) {
    const v = r.work_zone_id
    if (v === null) out.work_zone_id = null
    else if (typeof v === 'string' && v) out.work_zone_id = v
  }
  if ('commute_mode' in r) {
    const v = r.commute_mode
    if (v === null) out.commute_mode = null
    else if (MODES.includes(v as CommuteMode)) out.commute_mode = v as CommuteMode
  }
  if ('office_days' in r) {
    const v = r.office_days
    if (v === null) out.office_days = null
    else if (typeof v === 'number' && Number.isInteger(v) && v >= 0 && v <= 5) out.office_days = v
  }
  if ('people' in r && Array.isArray(r.people)) {
    out.people = r.people.filter(isPerson).slice(0, 50)
  }
  return out
}

/**
 * Profile fields recoverable without an account: the explorer already keeps income and the work
 * hub in homefit_search_options and people in their own key, so anonymous users still get the
 * overlay once they've set those in the explorer.
 */
export function readLocalProfile(): Partial<UserProfile> {
  const out: Partial<UserProfile> = {}
  try {
    const opts = JSON.parse(localStorage.getItem('homefit_search_options') ?? 'null')
    const income = opts?.household_income
    if (typeof income === 'number' && income > 0) out.household_income = income
    const zone = opts?.filters?.workZoneId
    if (typeof zone === 'string' && zone) out.work_zone_id = zone
    const mode = opts?.commute_mode
    if (MODES.includes(mode)) out.commute_mode = mode
    const days = opts?.office_days
    if (typeof days === 'number' && Number.isInteger(days) && days >= 0 && days <= 5) out.office_days = days
    const homeName = opts?.current_home_match
    if (typeof homeName === 'string' && homeName) {
      const cost = opts?.current_home_monthly_cost
      out.current_home = { name: homeName, monthly_cost: typeof cost === 'number' && cost > 0 ? cost : null }
    }
  } catch { /* ignore */ }
  const people = loadPeople()
  if (people.length) out.people = people
  return out
}

export async function fetchProfile(): Promise<Partial<UserProfile> | null> {
  try {
    const res = await fetch('/api/me/profile')
    if (!res.ok) return null
    const data = await res.json()
    return data?.profile ? sanitizeProfile(data.profile) : null
  } catch {
    return null
  }
}

/** Resolves true when the server stored the patch. Local state still applies when it didn't. */
export async function saveProfile(patch: Partial<UserProfile>): Promise<boolean> {
  try {
    const res = await fetch('/api/me/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
      keepalive: true,
    })
    return res.ok
  } catch {
    return false
  }
}
