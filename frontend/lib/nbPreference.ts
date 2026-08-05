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

  // OWA: preferred mean → lead slot; remaining components fill lower slots in desc order.
  // Lead weight scales with the preferred score so high-scoring preferred dimensions dominate more.
  const preferred = prefVals.reduce((a, b) => a + b, 0) / prefVals.length
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

