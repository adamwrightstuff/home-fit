import type { SocialConnectionTier } from '@/lib/reweight'

export interface SocialConnectionPerson {
  id: string
  /** User-entered, e.g. "Mom" or "Sarah & Jake". Falls back to the address if left blank. */
  label: string
  address: string
  lat: number
  lon: number
  tier: SocialConnectionTier
}

/**
 * Long-lived on purpose, unlike the sessionStorage-backed search filters -- who you're close
 * to doesn't change every visit, so re-entering it each session would be the wrong tradeoff.
 */
const STORAGE_KEY = 'homefit_people_you_know'

export function loadPeople(): SocialConnectionPerson[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (p): p is SocialConnectionPerson =>
        p && typeof p.id === 'string' && typeof p.lat === 'number' && typeof p.lon === 'number' &&
        (p.tier === 'close' || p.tier === 'acquaintance')
    )
  } catch {
    return []
  }
}

export function savePeople(people: SocialConnectionPerson[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(people))
  } catch {
    // Best-effort; a private window or full storage just means it won't persist this time.
  }
}

export type GeocodePersonResult = { error: string } | { lat: number; lon: number; address: string }

export async function geocodePerson(address: string): Promise<GeocodePersonResult> {
  try {
    const res = await fetch(`/api/geocode?location=${encodeURIComponent(address)}`)
    const data = await res.json().catch(() => ({}))
    if (!res.ok || typeof data?.lat !== 'number') {
      return { error: data?.detail || "We couldn't find that address." }
    }
    return { lat: data.lat, lon: data.lon, address }
  } catch {
    return { error: 'Location service is temporarily unavailable.' }
  }
}
