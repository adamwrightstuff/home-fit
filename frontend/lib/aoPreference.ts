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

  const preferred = Math.max(...prefVals)
  const others = keys
    .filter((k) => !targets.has(k))
    .map((k) => normalized[k])
    .filter((v): v is number => typeof v === 'number')
    .sort((a, b) => b - a)

  const dynamicLead = Math.min(1.0, 0.62 + 0.38 * (preferred / 100))
  const ranked = [preferred, ...others]
  const weights = [dynamicLead, ...AO_OWA_WEIGHTS.slice(1, ranked.length)]
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

  const dynamicLead = Math.min(1.0, 0.62 + 0.38 * (prefVal / 100))
  const ranked = [prefVal, ...others]
  const weights = [dynamicLead, ...WATERFRONT_OWA_WEIGHTS.slice(1, ranked.length)]
  const tot = weights.reduce((a, b) => a + b, 0) || 1
  return Math.round((ranked.reduce((sum, s, i) => sum + (weights[i] / tot) * s, 0)) * 100) / 100
}

// ── Gradient multiplier preference model ─────────────────────────────────────
// Replaces the true-AND filter this used to be (6d7b639) for the same reason as
// nbPreference.ts's nbPreferenceMultiplier: a hard floor gate removes a place
// from results entirely the moment ANY selected trait misses its floor, which
// risks an empty results page and treats "just below the 40th percentile" the
// same as "has none of this at all." This keeps each selected sub-component
// checked independently against its own floor, but turns the gate into a
// multiplier (1.0 at/above floor, steep falloff below) instead of a pass/fail,
// and multiplies every selected trait's multiplier together so a place missing
// one of several picks still gets compounded down. Never mutates
// active_outdoors.score -- only used to weight sort order (see
// computePreferenceMultiplier in catalog-page-client.tsx).
//
// Floors are the 40th percentile of each raw component (normalized to 0-100)
// across the current NYC/SF/LA/Seattle catalog -- see
// scripts/baselines/compute_preference_floors.py.
export const AO_PREFERENCE_FLOOR: Record<AoNumericKey, number> = {
  daily_urban_outdoors: 57,
  wild_adventure: 70,
  waterfront_lifestyle: 65,
}

// 40th percentile of each waterfront sub-type, computed only over places where
// that sub-type is actually nonzero (most places are inland and score a flat 0 on
// e.g. bay_harbor, so an all-places percentile would just be 0 and gate nothing --
// see scripts/baselines/compute_preference_floors.py). bay_harbor has zero
// nonzero places in the current 4-metro catalog, so it falls back to the
// lake_river floor as a placeholder; recompute once a real bay/harbor-winning
// place exists in the catalog.
export const AO_WATERFRONT_SUBTYPE_FLOOR: Record<WaterfrontSubPreference, number> = {
  ocean_beach: 85,
  lake_river: 65,
  bay_harbor: 65,
}

// See nbPreference.ts's NB_TRAIT_EXPONENT for the rationale (steep but not a cliff).
const AO_TRAIT_EXPONENT = 4

/**
 * Gradient multiplier (0-1] for how well this place matches every selected AO
 * sub-preference, compounded across preferences. 1.0 when no preferences are
 * selected or the place has no AO breakdown (null-safe, never penalizes a gap).
 * When `waterfrontSub` is given and `waterfront` is selected, also folds in a
 * multiplier for that specific water type's own floor (not just any
 * waterfront_lifestyle score).
 */
export function aoPreferenceMultiplier(
  breakdown: AoBreakdown | undefined | null,
  preferences: AoPreference[],
  waterfrontSub?: WaterfrontSubPreference | null,
): number {
  if (!breakdown || preferences.length === 0) return 1
  let multiplier = 1
  for (const pref of preferences) {
    const key = PREFERENCE_AO_COMPONENTS[pref]
    const raw = breakdown[key]
    if (typeof raw === 'number') {
      const normalized = Math.min(100, (raw / AO_COMPONENT_MAX[key]) * 100)
      const floor = AO_PREFERENCE_FLOOR[key] ?? 0
      const ratio = floor > 0 ? Math.min(1, normalized / floor) : 1
      multiplier *= ratio ** AO_TRAIT_EXPONENT
    }
    if (pref === 'waterfront' && waterfrontSub) {
      const wb = breakdown.waterfront_breakdown
      const subVal = wb?.[waterfrontSub] ?? 0
      const subFloor = AO_WATERFRONT_SUBTYPE_FLOOR[waterfrontSub] ?? 0
      const ratio = subFloor > 0 ? Math.min(1, subVal / subFloor) : 1
      multiplier *= ratio ** AO_TRAIT_EXPONENT
    }
  }
  return multiplier
}
