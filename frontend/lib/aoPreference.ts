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

// Raw contribution caps from active_outdoors.py (daily≤35, wild≤40, waterfront≤25, sum=100).
const AO_COMPONENT_MAX: Record<keyof AoBreakdown, number> = {
  daily_urban_outdoors: 35,
  wild_adventure: 40,
  waterfront_lifestyle: 25,
}

// OWA weights mirror the NB V9 model: lead slot gets 0.62, others fill down.
const AO_OWA_WEIGHTS = [0.62, 0.25, 0.13]

/**
 * Re-weight the Active Outdoors score toward selected sub-components using OWA re-weighting.
 * Normalizes each raw contribution to 0-100 first (daily≤30, wild≤50, waterfront≤20),
 * then forces the preferred component into the OWA lead slot (0.62) while the others still
 * contribute in the lower slots. Mirrors the NB V9 preference approach so behavior is consistent.
 */
export function applyAoPreferences(
  breakdown: AoBreakdown | undefined | null,
  preferences: AoPreference[],
): number | null {
  if (!breakdown || preferences.length === 0) return null

  const keys = Object.keys(AO_COMPONENT_MAX) as (keyof AoBreakdown)[]
  const normalized: Partial<Record<keyof AoBreakdown, number>> = {}
  for (const key of keys) {
    const raw = breakdown[key]
    if (typeof raw === 'number') {
      normalized[key] = Math.min(100, (raw / AO_COMPONENT_MAX[key]) * 100)
    }
  }

  const targets = new Set(preferences.map((p) => PREFERENCE_AO_COMPONENTS[p]))
  const prefVals = Array.from(targets).map((t) => normalized[t]).filter((v): v is number => typeof v === 'number')
  if (prefVals.length === 0) return null

  const preferred = prefVals.reduce((a, b) => a + b, 0) / prefVals.length
  const others = keys
    .filter((k) => !targets.has(k))
    .map((k) => normalized[k])
    .filter((v): v is number => typeof v === 'number')
    .sort((a, b) => b - a)

  const ranked = [preferred, ...others]
  const weights = AO_OWA_WEIGHTS.slice(0, ranked.length)
  const tot = weights.reduce((a, b) => a + b, 0) || 1
  return Math.round((ranked.reduce((sum, s, i) => sum + (weights[i] / tot) * s, 0)) * 100) / 100
}
