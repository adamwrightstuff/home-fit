export type AoPreference = 'local_parks' | 'trails_regional' | 'waterfront'

export const AO_PREFERENCE_LABELS: Record<AoPreference, string> = {
  local_parks: 'Local Parks',
  trails_regional: 'Trails & Regional Parks',
  waterfront: 'Waterfront',
}

export type WaterfrontSubPreference = 'ocean_beach' | 'lake_river' | 'bay_harbor'

export const WATERFRONT_SUB_LABELS: Record<WaterfrontSubPreference, string> = {
  ocean_beach: 'Ocean & Beach',
  lake_river: 'Lakes & Rivers',
  bay_harbor: 'Bays & Harbors',
}

export interface WaterfrontBreakdown {
  ocean_beach?: number
  lake_river?: number
  bay_harbor?: number
}

export interface AoBreakdown {
  daily_urban_outdoors?: number
  wild_adventure?: number
  waterfront_lifestyle?: number
  waterfront_breakdown?: WaterfrontBreakdown
}

// Numeric-only keys of AoBreakdown (excludes waterfront_breakdown which is an object).
type AoNumericKey = 'daily_urban_outdoors' | 'wild_adventure' | 'waterfront_lifestyle'

const PREFERENCE_AO_COMPONENTS: Record<AoPreference, AoNumericKey> = {
  local_parks: 'daily_urban_outdoors',
  trails_regional: 'wild_adventure',
  waterfront: 'waterfront_lifestyle',
}

// Raw contribution caps from active_outdoors.py (daily≤35, wild≤50, waterfront≤25, sum=110 capped at 100).
const AO_COMPONENT_MAX: Record<AoNumericKey, number> = {
  daily_urban_outdoors: 35,
  wild_adventure: 50,
  waterfront_lifestyle: 25,
}

// OWA weights mirror the NB V9 model: lead slot gets 0.62, others fill down.
const AO_OWA_WEIGHTS = [0.62, 0.25, 0.13]

/**
 * Re-weight the Active Outdoors score toward selected sub-components using OWA re-weighting.
 * Normalizes each raw contribution to 0-100 first (daily≤35, wild≤50, waterfront≤25),
 * then forces the preferred component into the OWA lead slot (0.62) while the others still
 * contribute in the lower slots. Mirrors the NB V9 preference approach so behavior is consistent.
 */
export function applyAoPreferences(
  breakdown: AoBreakdown | undefined | null,
  preferences: AoPreference[],
): number | null {
  if (!breakdown || preferences.length === 0) return null

  const keys = Object.keys(AO_COMPONENT_MAX) as AoNumericKey[]
  const normalized: Partial<Record<AoNumericKey, number>> = {}
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

// OWA weights for waterfront sub-preference reweighting (3 categories).
const WATERFRONT_OWA_WEIGHTS = [0.62, 0.25, 0.13]

/**
 * Re-weight the waterfront_lifestyle component toward a specific water type using OWA.
 * Sub-scores (ocean_beach, lake_river, bay_harbor) are already normalized to 0-100 by
 * the backend. The preferred type goes into the OWA lead slot; others fill the tail.
 * Returns null when waterfront_breakdown data is absent (pre-existing scores).
 */
export function applyWaterfrontPreference(
  breakdown: AoBreakdown | undefined | null,
  preference: WaterfrontSubPreference,
): number | null {
  const wb = breakdown?.waterfront_breakdown
  if (!wb) return null

  const keys: WaterfrontSubPreference[] = ['ocean_beach', 'lake_river', 'bay_harbor']
  const vals = keys.map((k) => wb[k] ?? 0)
  if (vals.every((v) => v === 0)) return null

  const prefIdx = keys.indexOf(preference)
  const prefVal = vals[prefIdx]
  // A place with zero of the preferred water type gets no cross-category boost.
  if (prefVal === 0) return 0
  const others = vals.filter((_, i) => i !== prefIdx).sort((a, b) => b - a)

  const ranked = [prefVal, ...others]
  const weights = WATERFRONT_OWA_WEIGHTS.slice(0, ranked.length)
  const tot = weights.reduce((a, b) => a + b, 0) || 1
  return Math.round((ranked.reduce((sum, s, i) => sum + (weights[i] / tot) * s, 0)) * 100) / 100
}
