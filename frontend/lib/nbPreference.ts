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
