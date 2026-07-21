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

/**
 * Re-weight the Active Outdoors score toward selected sub-components.
 * Returns null if breakdown is missing or no preferences selected (caller keeps stored score).
 */
export function applyAoPreferences(
  breakdown: AoBreakdown | undefined | null,
  preferences: AoPreference[],
): number | null {
  if (!breakdown || preferences.length === 0) return null
  const vals = preferences
    .map((p) => breakdown[PREFERENCE_AO_COMPONENTS[p]])
    .filter((v): v is number => typeof v === 'number')
  if (vals.length === 0) return null
  return Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) / 100
}
