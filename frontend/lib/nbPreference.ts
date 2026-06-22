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
  canopy: ['canopy_score', 'gvi_score'],
}

export interface V9Breakdown {
  gvi_score?: number
  water_score?: number
  canopy_score?: number
  topo_score?: number
  landcover_score?: number
  bio_score?: number
}

/**
 * Re-score natural beauty for a scenery preference from the stored V9 component scores.
 * Returns null if the V9 breakdown is missing (caller keeps the stored score).
 */
export function applyNbPreferenceV9(
  v9: V9Breakdown | undefined | null,
  preference: NbPreference,
): number | null {
  if (!v9) return null
  const comp: Record<string, number> = {}
  for (const k of V9_COMPONENT_KEYS) {
    const v = (v9 as Record<string, unknown>)[k]
    if (typeof v === 'number') comp[k] = v
  }
  const targets = PREFERENCE_V9_COMPONENTS[preference] ?? []
  const prefVals = targets.map((t) => comp[t]).filter((v) => typeof v === 'number')
  if (prefVals.length === 0) return null
  const preferred = prefVals.reduce((a, b) => a + b, 0) / prefVals.length
  const others = Object.entries(comp)
    .filter(([k]) => !targets.includes(k))
    .map(([, v]) => v)
    .sort((a, b) => b - a)
  const ranked = [preferred, ...others]
  const w = V9_OWA_WEIGHTS.slice(0, ranked.length)
  const tot = w.reduce((a, b) => a + b, 0) || 1
  return Math.round(ranked.reduce((s, v, i) => s + (w[i] / tot) * v, 0) * 100) / 100
}

/**
 * Compute a preference-adjusted NB score.
 * Returns null if the breakdown lacks the raw component fields (pre-rescore data).
 */
export function adjustNbScore(
  storedScore: number,
  breakdown: NbBreakdown,
  waterProximityType: string | undefined,
  preference: NbPreference,
  placeAreaType?: string,
): number | null {
  const {
    enhancer_bonus_raw,
    nb_topo_raw,
    nb_topo_base,
    nb_landcover_raw,
    nb_landcover,
    nb_water_raw,
    nb_water,
    nb_scenic_cap,
  } = breakdown

  // Fall back gracefully if rescore hasn't populated raw fields yet
  if (
    nb_topo_raw === undefined ||
    nb_landcover_raw === undefined ||
    nb_water_raw === undefined ||
    enhancer_bonus_raw === undefined
  ) {
    return null
  }

  const oldContext = enhancer_bonus_raw
  const topoBonus = (enhancer_bonus_raw ?? 0) - (nb_topo_base ?? 0) - (nb_landcover ?? 0) - (nb_water ?? 0)

  const prof = PREFERENCE_PROFILES[preference]
  const ak = areaKey(placeAreaType)
  const cw = prof.context_weights[ak] ?? prof.context_weights['urban_core']

  const wtw = prof.water_type_weights ?? DEFAULT_WATER_TYPE
  const wMult = waterTypeMult(waterProximityType, wtw)

  const newContext =
    nb_topo_raw * cw.topography +
    topoBonus +
    nb_landcover_raw * cw.landcover +
    nb_water_raw * wMult * cw.water

  const cap = nb_scenic_cap ?? 70.0
  const oldScenic = Math.min(cap, Math.min(NATURAL_ENHANCER_CAP, oldContext) * 2.0)
  const newScenic = Math.min(cap, Math.min(NATURAL_ENHANCER_CAP, newContext) * 2.0)

  const deltaScenic = newScenic - oldScenic
  const deltaUplift = contextUplift(newContext) - contextUplift(oldContext)

  return Math.max(0, Math.min(100, storedScore + deltaScenic + deltaUplift))
}

// --- combined_weight TS port (mirrors pillars/neighborhood_beauty.py _combined_weight) ---

// Mirrors _LOG_LO / _LOG_HI in neighborhood_beauty.py: catalog density anchors (p1≈500, p95≈95474).
const NB_LOG_LO = Math.log10(500)
const NB_LOG_HI = Math.log10(95474)

// Mirrors _AREA_TYPE_FLOOR in neighborhood_beauty.py.
const NB_AREA_TYPE_FLOOR: Record<string, number> = {
  urban_core: 0.65,
  historic_urban: 0.65,
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x))
}

function densityWeight(density: number | null | undefined): number | null {
  if (density === null || density === undefined || density <= 0) return null
  const d = clamp01((Math.log10(density) - NB_LOG_LO) / (NB_LOG_HI - NB_LOG_LO))
  return 0.25 + 0.7 * d
}

/** TS mirror of pillars/neighborhood_beauty.py's combined_weight(): weight on built_beauty. */
export function combinedWeight(density: number | null | undefined, effectiveAreaType?: string | null): number {
  const w = densityWeight(density)
  const floor = effectiveAreaType ? NB_AREA_TYPE_FLOOR[effectiveAreaType] : undefined
  if (w === null) return floor !== undefined ? floor : 0.5
  return floor !== undefined ? Math.max(w, floor) : w
}

/**
 * Recompute the full blended neighborhood_beauty score after a client-side natural-beauty
 * preference change, by reapplying the same density+area-type weight the backend uses.
 * Returns null if the natural-beauty adjustment itself can't be computed (pre-rescore data).
 */
export function adjustNeighborhoodBeautyScore(
  builtScore: number,
  storedNaturalScore: number,
  breakdown: NbBreakdown,
  waterProximityType: string | undefined,
  preference: NbPreference,
  density: number | null | undefined,
  effectiveAreaType?: string | null,
): number | null {
  const adjustedNatural = adjustNbScore(storedNaturalScore, breakdown, waterProximityType, preference, effectiveAreaType ?? undefined)
  if (adjustedNatural === null) return null
  const w = combinedWeight(density, effectiveAreaType)
  return Math.round((w * builtScore + (1 - w) * adjustedNatural) * 100) / 100
}

/**
 * Recompute the blended neighborhood_beauty score from a catalog row's nested
 * `details.natural_beauty.v9_breakdown`, after re-biasing toward a scenery preference.
 * Mirrors adjustNeighborhoodBeautyScore but for V9-scored catalog data (no nb_topo_raw/
 * nb_water_raw fields available — those are V7-only). Returns null if the breakdown is
 * missing the V9 component scores (no rescore data to re-bias).
 */
export function adjustNeighborhoodBeautyScoreV9(
  builtScore: number,
  storedNaturalScore: number,
  v9: V9Breakdown | undefined | null,
  preference: NbPreference,
  density: number | null | undefined,
  effectiveAreaType?: string | null,
): number | null {
  const adjustedNatural = applyNbPreferenceV9(v9, preference)
  if (adjustedNatural === null) return null
  const w = combinedWeight(density, effectiveAreaType)
  return Math.round((w * builtScore + (1 - w) * adjustedNatural) * 100) / 100
}

/**
 * Pre-migration saved scores / cache entries store standalone `built_beauty` and
 * `natural_beauty` pillar entries with no `neighborhood_beauty` key at all. Synthesize one
 * client-side, reapplying the real density+area-type blend, so legacy data still renders on
 * a surface that now only ever looks for `neighborhood_beauty`. No-op if already merged.
 */
export function withSynthesizedNeighborhoodBeauty(
  livabilityPillars: Record<string, any> | null | undefined,
): Record<string, any> {
  if (!livabilityPillars || typeof livabilityPillars !== 'object') return livabilityPillars ?? {}
  if (livabilityPillars.neighborhood_beauty) return livabilityPillars
  const built = livabilityPillars.built_beauty
  const natural = livabilityPillars.natural_beauty
  if (!built && !natural) return livabilityPillars

  const builtScore = typeof built?.score === 'number' ? built.score : 0
  const naturalScore = typeof natural?.score === 'number' ? natural.score : 0
  const density = built?.details?.density ?? natural?.details?.density ?? null
  const effectiveAreaType = built?.details?.effective_area_type ?? natural?.details?.effective_area_type ?? null
  const w = built && natural ? combinedWeight(density, effectiveAreaType) : built ? 1 : 0
  const score = Math.round((w * builtScore + (1 - w) * naturalScore) * 100) / 100
  const weight = (built?.weight ?? 0) + (natural?.weight ?? 0)
  const contribution = (built?.contribution ?? 0) + (natural?.contribution ?? 0)

  const synthesized = {
    score,
    weight,
    importance_level: built?.importance_level ?? natural?.importance_level ?? null,
    contribution,
    built_beauty_score: builtScore,
    natural_beauty_score: naturalScore,
    built_weight: w,
    breakdown: {
      built_beauty_score: builtScore,
      natural_beauty_score: naturalScore,
      built_weight: w,
      effective_area_type: effectiveAreaType,
      density,
    },
    summary: {
      built_beauty: built?.summary ?? {},
      natural_beauty: natural?.summary ?? {},
      built_weight: w,
    },
    details: {
      built_beauty: built?.details ?? {},
      natural_beauty: natural?.details ?? {},
      built_weight: w,
      effective_area_type: effectiveAreaType,
      density,
      source: 'neighborhood_beauty_legacy_synthesized',
    },
    confidence: built?.confidence ?? natural?.confidence ?? 0,
    data_quality: built?.data_quality ?? natural?.data_quality ?? {},
    status: built?.status ?? natural?.status,
  }

  return { ...livabilityPillars, neighborhood_beauty: synthesized }
}
