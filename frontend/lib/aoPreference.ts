export type AoPreference = 'local_parks' | 'trails_regional' | 'waterfront'

export const AO_PREFERENCE_LABELS: Record<AoPreference, string> = {
  local_parks: 'Local Parks',
  trails_regional: 'Trails & Regional Parks',
  waterfront: 'Waterfront',
}

export interface AoBreakdown {
  daily_urban_outdoors?: number
  wild_adventure?: number
  waterfront_lifestyle?: number
}

const PREFERENCE_AO_COMPONENTS: Record<AoPreference, keyof AoBreakdown> = {
  local_parks: 'daily_urban_outdoors',
  trails_regional: 'wild_adventure',
  waterfront: 'waterfront_lifestyle',
}

// Raw contribution caps from active_outdoors.py: daily=30, wild=50, waterfront=20 (sum=100)
const AO_COMPONENT_MAX: Record<keyof AoBreakdown, number> = {
  daily_urban_outdoors: 30,
  wild_adventure: 50,
  waterfront_lifestyle: 20,
}

/**
 * Re-weight the Active Outdoors score toward selected sub-components.
 * Normalizes each component to 0-100 before averaging — the raw breakdown values are
 * contributions that sum to 100 (daily≤30, wild≤50, waterfront≤20), not 0-100 scores.
 * Returns null if breakdown is missing or no preferences selected (caller keeps stored score).
 */
export function applyAoPreferences(
  breakdown: AoBreakdown | undefined | null,
  preferences: AoPreference[],
): number | null {
  if (!breakdown || preferences.length === 0) return null
  const vals = preferences
    .map((p) => {
      const key = PREFERENCE_AO_COMPONENTS[p]
      const raw = breakdown[key]
      if (typeof raw !== 'number') return undefined
      return Math.min(100, (raw / AO_COMPONENT_MAX[key]) * 100)
    })
    .filter((v): v is number => typeof v === 'number')
  if (vals.length === 0) return null
  return Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) / 100
}
