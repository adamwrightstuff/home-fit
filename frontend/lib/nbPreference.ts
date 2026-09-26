/**
 * Client-side Natural Beauty preference re-weighting.
 *
 * After a rescore populates nb_topo_raw / nb_landcover_raw / nb_water_raw / nb_topo_base /
 * nb_landcover / nb_water / nb_scenic_cap in the NB breakdown, this module can compute a
 * preference-adjusted NB score without any API call.
 *
 * Formula mirror of natural_beauty.py preference profiles + scoring pipeline.
 */

export type NbPreference = 'mountains' | 'ocean' | 'lakes_rivers' | 'canopy'

// ── Built Environment Preference ─────────────────────────────────────────────

export type BuiltEnvPreference = 'urban_core' | 'urban_residential' | 'suburban' | 'exurban' | 'rural'

export const BUILT_ENV_LABELS: Record<BuiltEnvPreference, string> = {
  urban_core: 'Urban Core',
  urban_residential: 'Urban Neighborhood',
  suburban: 'Suburban',
  exurban: 'Exurban',
  rural: 'Rural',
}

// Density spectrum index: 0 (least dense) → 4 (most dense)
const AREA_TYPE_INDEX: Record<string, number> = {
  rural: 0,
  exurban: 1,
  suburban: 2,
  urban_residential: 3,
  urban_core: 4,
}

/**
 * Area type match score (0–100) for a place given the user's preferred area type.
 * Asymmetric: being denser than preferred is penalized more than being less dense,
 * since most users who want suburban are more tolerant of quiet exurban than dense urban.
 */
export function builtEnvMatchScore(
  placeAreaType: string | null | undefined,
  preference: BuiltEnvPreference,
): number {
  const normalized = (placeAreaType ?? '').toLowerCase().replace(/-/g, '_')
  const placeIdx = AREA_TYPE_INDEX[normalized] ?? AREA_TYPE_INDEX['suburban']
  const prefIdx = AREA_TYPE_INDEX[preference]
  const diff = placeIdx - prefIdx // positive = denser than preferred

  if (diff === 0) return 100
  if (diff > 0) {
    // Too dense — steeper penalty
    if (diff === 1) return 60
    if (diff === 2) return 30
    return 5
  } else {
    // Too sparse — gentler penalty
    const d = Math.abs(diff)
    if (d === 1) return 75
    if (d === 2) return 50
    return 20
  }
}

export const NB_PREFERENCE_LABELS: Record<NbPreference, string> = {
  mountains: 'Mountains',
  ocean: 'Ocean / Coast',
  lakes_rivers: 'Lakes & Rivers',
  canopy: 'Tree Canopy',
}

// Mirrors NATURAL_BEAUTY_PREFERENCE_PROFILES in natural_beauty.py
// area_key: 'rural' | 'suburban' | 'urban_core'
type ContextWeights = { topography: number; landcover: number; water: number }
type WaterTypeWeights = { coast: number; lake: number; river: number } | null

interface PrefProfile {
  context_weights: Record<string, ContextWeights>
  water_type_weights: WaterTypeWeights
}

const PREFERENCE_PROFILES: Record<NbPreference, PrefProfile> = {
  mountains: {
    context_weights: {
      rural:      { topography: 0.75, landcover: 0.15, water: 0.10 },
      suburban:   { topography: 0.68, landcover: 0.20, water: 0.12 },
      urban_core: { topography: 0.68, landcover: 0.20, water: 0.12 },
    },
    water_type_weights: null,
  },
  ocean: {
    context_weights: {
      rural:      { topography: 0.25, landcover: 0.15, water: 0.60 },
      suburban:   { topography: 0.20, landcover: 0.15, water: 0.65 },
      urban_core: { topography: 0.20, landcover: 0.15, water: 0.65 },
    },
    water_type_weights: { coast: 0.80, lake: 0.10, river: 0.10 },
  },
  lakes_rivers: {
    context_weights: {
      rural:      { topography: 0.28, landcover: 0.17, water: 0.55 },
      suburban:   { topography: 0.22, landcover: 0.18, water: 0.60 },
      urban_core: { topography: 0.22, landcover: 0.18, water: 0.60 },
    },
    water_type_weights: { coast: 0.15, lake: 0.55, river: 0.30 },
  },
  canopy: {
    context_weights: {
      rural:      { topography: 0.40, landcover: 0.45, water: 0.15 },
      suburban:   { topography: 0.35, landcover: 0.50, water: 0.15 },
      urban_core: { topography: 0.35, landcover: 0.50, water: 0.15 },
    },
    water_type_weights: null,
  },
}

// Default water-type weights (mirrors WATER_TYPE_WEIGHTS_DEFAULT)
const DEFAULT_WATER_TYPE: WaterTypeWeights = { coast: 0.60, lake: 0.30, river: 0.10 }

// Mirrors NATURAL_ENHANCER_CAP = 25.0
const NATURAL_ENHANCER_CAP = 25.0

function waterTypeMult(waterType: string | undefined, weights: WaterTypeWeights): number {
  if (!weights || !waterType) return 1.0
  const t = waterType.toLowerCase()
  if (t === 'coast' || t === 'ocean' || t === 'coastline' || t === 'bay' || t === 'harbor' || t === 'sea') {
    return (weights.coast ?? 0.60) / (DEFAULT_WATER_TYPE?.coast ?? 0.60)
  }
  if (t === 'lake' || t === 'reservoir') {
    return (weights.lake ?? 0.30) / (DEFAULT_WATER_TYPE?.lake ?? 0.30)
  }
  // river, stream, canal, etc.
  return (weights.river ?? 0.10) / (DEFAULT_WATER_TYPE?.river ?? 0.10)
}

function contextUplift(contextBonus: number): number {
  if (contextBonus >= 20.0) return 15.0
  if (contextBonus >= 10.0) return 5.0 + ((contextBonus - 10.0) / 10.0) * 10.0
  return 0.0
}

function areaKey(areaType: string | undefined): string {
  const t = (areaType || '').toLowerCase()
  if (t.includes('rural') || t.includes('exurban')) return 'rural'
  if (t.includes('suburban')) return 'suburban'
  return 'urban_core'
}

export interface NbBreakdown {
  tree_score_0_50?: number
  enhancer_bonus_raw?: number
  nb_topo_raw?: number
  nb_topo_base?: number
  nb_landcover_raw?: number
  nb_landcover?: number
  nb_water_raw?: number
  nb_water?: number
  nb_scenic_cap?: number
}

// ── V9 preference (current model) ────────────────────────────────────────────
// Mirrors pillars/natural_beauty.py apply_v9_preference. The V9 score is an Ordered
// Weighted Average of six per-dimension scores; a preference forces its dimension into
// the OWA lead slot (0.62) so it becomes the lead criterion. Reads the stored
// details.v9_breakdown component scores — no V7 scenic-bonus math.
const V9_OWA_WEIGHTS = [0.62, 0.25, 0.1, 0.02, 0.01, 0.0]
const V9_COMPONENT_KEYS = [
  'gvi_score', 'water_score', 'canopy_score', 'topo_score', 'landcover_score', 'bio_score',
] as const
const PREFERENCE_V9_COMPONENTS: Record<NbPreference, string[]> = {
  mountains: ['topo_score'],
  ocean: ['water_score'],
  lakes_rivers: ['water_score'],
  canopy: ['gvi_score'],
}

export interface V9Breakdown {
  gvi_score?: number
  water_score?: number
  canopy_score?: number
  topo_score?: number
  landcover_score?: number
  bio_score?: number
  inputs?: { water_type?: string }
}

/**
 * Re-score natural beauty for one or more scenery preferences using full OWA re-weighting.
 * Mirrors apply_v9_preference() in natural_beauty.py: forces the preferred component(s) into
 * the OWA lead slot (0.62) so they become the lead criterion, while all other components still
 * fill the lower slots. This means a place strong in its preferred dimension stays high; a place
 * weak in it drops — but the drop is tempered by the other components, unlike returning the raw
 * component score which ignores everything else.
 */
export function applyNbPreferencesV9(
  v9: V9Breakdown | undefined | null,
  preferences: NbPreference[],
): number | null {
  if (!v9 || preferences.length === 0) return null
  const waterType = v9.inputs?.water_type

  // Build effective per-component scores, applying water-type penalty where needed.
  const effective: Partial<Record<string, number>> = {}
  for (const key of V9_COMPONENT_KEYS) {
    const val = (v9 as Record<string, unknown>)[key]
    if (typeof val === 'number') effective[key] = val
  }
  if (waterType) {
    for (const pref of preferences) {
      if ((pref === 'ocean' || pref === 'lakes_rivers') && typeof effective['water_score'] === 'number') {
        const isCoastal = /ocean|coast|bay|harbor|sea/i.test(waterType)
        const isLakeRiver = /lake|reservoir|river|stream|canal/i.test(waterType)
        const match = pref === 'ocean' ? isCoastal : isLakeRiver
        if (!match) effective['water_score'] = effective['water_score']! * 0.25
      }
    }
  }

  // Collect preferred targets (deduped across all selected preferences).
  const targets = new Set(preferences.flatMap((p) => PREFERENCE_V9_COMPONENTS[p] ?? []))
  const prefVals = Array.from(targets).map((t) => effective[t]).filter((v): v is number => typeof v === 'number')
  if (prefVals.length === 0) return null

  // OWA: best preferred component → lead slot; remaining components fill lower slots in desc order.
  // Using max (not mean) so a place strong in ANY preferred dimension isn't penalised for
  // a weaker second preference — both still contribute in lower slots via `others`.
  const preferred = Math.max(...prefVals)
  const others = Object.entries(effective)
    .filter(([k]) => !targets.has(k))
    .map(([, v]) => v as number)
    .sort((a, b) => b - a)
  const dynamicLead = Math.min(1.0, 0.62 + 0.38 * (preferred / 100))
  const ranked = [preferred, ...others]
  const weights = [dynamicLead, ...V9_OWA_WEIGHTS.slice(1, ranked.length)]
  const tot = weights.reduce((a, b) => a + b, 0) || 1
  return Math.round((ranked.reduce((sum, s, i) => sum + (weights[i] / tot) * s, 0)) * 100) / 100
}

/** @deprecated use applyNbPreferencesV9 */
export function applyNbPreferenceV9(
  v9: V9Breakdown | undefined | null,
  preference: NbPreference,
): number | null {
  return applyNbPreferencesV9(v9, [preference])
}

// ── Gradient multiplier preference model ─────────────────────────────────────
// Replaces the true-AND filter this used to be (6d7b639). That filter fixed the
// OWA blend's real bug (canopy standing in as gvi_score got buried under a
// stronger water_score for an ocean+canopy pick) but traded it for a new one:
// a hard floor gate removes a place from results entirely the moment ANY
// selected trait misses its floor, which risks an empty results page and treats
// "slightly below the 40th percentile" the same as "has none of this at all."
//
// This keeps the AND filter's real fix (each selected trait checked against its
// own real component, not diluted by unrelated ones) but turns the gate into a
// multiplier: 1.0 at/above the floor, dropping steeply (not instantly) below it.
// Multipliers for every selected trait are then multiplied together -- a place
// missing one of several selected traits gets compounded down even if its other
// traits are perfect, so multi-trait matches still rise above single-trait ones,
// but nothing is ever removed from the list outright. Never mutates the NB score
// -- only used to weight sort order (see computePreferenceMultiplier in
// catalog-page-client.tsx).
//
// Floors are the 40th percentile of each component across the current NYC/SF/LA/
// Seattle catalog -- see scripts/baselines/compute_preference_floors.py. Rerun
// that script and re-paste here if the catalog's composition changes enough to
// drift these (new metros, a big rescore).
export const NB_PREFERENCE_FLOOR: Record<string, number> = {
  gvi_score: 61,
  water_score: 11,
  canopy_score: 8,
  topo_score: 28,
  landcover_score: 1,
  bio_score: 1,
}

// Unlike the OWA blend's PREFERENCE_V9_COMPONENTS (which maps canopy -> gvi_score),
// this maps canopy to its own real component -- the actual bug fix.
const NB_PREFERENCE_TARGET: Record<NbPreference, keyof V9Breakdown> = {
  mountains: 'topo_score',
  ocean: 'water_score',
  lakes_rivers: 'water_score',
  canopy: 'canopy_score',
}

// How steeply a trait below its floor gets penalized. ratio**4 keeps ~66% credit
// at 90% of floor but crushes to ~6% at half of floor -- steep enough to sink a
// clear miss out of view without a hard cliff at the floor itself.
const NB_TRAIT_EXPONENT = 4

// water_type is a categorical fact (is the nearest water body actually ocean vs
// lake/river), not a magnitude -- there's no percentile to derive, so a mismatch
// gets a fixed heavy penalty instead. Missing water_type data is null-safe (no
// penalty), matching how every other filter in this catalog treats a data gap.
const NB_WATER_TYPE_MISMATCH_MULTIPLIER = 0.05

/**
 * Gradient multiplier (0-1] for how well this place matches every selected
 * scenery preference, compounded across preferences. 1.0 when no preferences
 * are selected or the place has no NB data (null-safe, never penalizes a gap).
 * Multiply this onto whatever score you're sorting by -- never onto
 * natural_beauty.score itself, so the pillar's weight keeps meaning the same
 * thing for every user and every composite that reads it stays consistent.
 */
export function nbPreferenceMultiplier(
  v9: V9Breakdown | undefined | null,
  preferences: NbPreference[],
): number {
  if (!v9 || preferences.length === 0) return 1
  const waterType = v9.inputs?.water_type ?? ''
  let multiplier = 1
  for (const pref of preferences) {
    const target = NB_PREFERENCE_TARGET[pref]
    const val = v9[target]
    if (typeof val === 'number') {
      const floor = NB_PREFERENCE_FLOOR[target] ?? 0
      const ratio = floor > 0 ? Math.min(1, val / floor) : 1
      multiplier *= ratio ** NB_TRAIT_EXPONENT
    }
    if (pref === 'ocean' && waterType && !/ocean|coast|bay|harbor|sea/i.test(waterType)) {
      multiplier *= NB_WATER_TYPE_MISMATCH_MULTIPLIER
    }
    if (pref === 'lakes_rivers' && waterType && !/lake|reservoir|river|stream|canal/i.test(waterType)) {
      multiplier *= NB_WATER_TYPE_MISMATCH_MULTIPLIER
    }
  }
  return multiplier
}

