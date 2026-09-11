import type { CatalogMapPlace } from '@/lib/catalogMapTypes'

const COASTAL_TYPES = new Set(['ocean', 'bay', 'river', 'lake'])

export const VIBE_WEIGHTS = {
  scene: 2.0,
  race:  1.5,
  bach:  2.0,
  dem:   0.75,
  scap:  1.5,
  gvi:   1.5,
  water: 0.75,
} as const

export type VibeKey = keyof typeof VIBE_WEIGHTS

export const VIBE_LABELS: Record<VibeKey, string> = {
  scene: 'Local scene',
  race:  'Diversity',
  bach:  'Education',
  dem:   'Politics',
  scap:  'Social capital',
  gvi:   'Greenery',
  water: 'Water',
}

export type VibeFeatures = {
  areaType: string | null
  waterBucket: 'coastal' | 'inland'
  waterType: string
  norm: Record<VibeKey, number>
  raw: Partial<Record<VibeKey, number | null>>
}

export type VibeTwinResult = {
  key: string
  place: CatalogMapPlace
  matchPct: number
  vibeFeatures: VibeFeatures
  queryFeatures: VibeFeatures
}

function deepGet(obj: unknown, ...keys: string[]): unknown {
  let cur: unknown = obj
  for (const k of keys) {
    if (cur === null || cur === undefined || typeof cur !== 'object') return null
    cur = (cur as Record<string, unknown>)[k]
  }
  return cur ?? null
}

function num(obj: unknown, ...keys: string[]): number | null {
  const v = deepGet(obj, ...keys)
  return typeof v === 'number' ? v : null
}

function str(obj: unknown, ...keys: string[]): string | null {
  const v = deepGet(obj, ...keys)
  return typeof v === 'string' ? v : null
}

export function extractVibeFeatures(place: CatalogMapPlace): VibeFeatures {
  const score = place.score as unknown as Record<string, unknown>
  const pillars = (score?.livability_pillars as Record<string, unknown>) ?? {}

  const areaType =
    str(score, 'data_quality_summary', 'area_classification', 'area_type') ||
    str(pillars, 'social_fabric', 'area_classification', 'area_type') ||
    str(pillars, 'diversity', 'area_classification', 'area_type')

  const scene = num(score, 'local_scene_score')
  const race  = num(pillars, 'diversity', 'breakdown', 'race_entropy')
  const bach  = num(pillars, 'diversity', 'education_attainment', 'bachelor_pct')
  const dem   = num(pillars, 'political_lean', 'breakdown', 'dem_pct_2024')
  const scap  = num(pillars, 'social_fabric', 'breakdown', 'social_capital')
  const gvi   = num(pillars, 'natural_beauty', 'v9_breakdown', 'gvi_score')
  const water = num(pillars, 'natural_beauty', 'v9_breakdown', 'water_score')

  const waterType =
    str(pillars, 'natural_beauty', 'v9_breakdown', 'inputs', 'water_type') ||
    str(pillars, 'natural_beauty', 'v9_breakdown', 'water_type') ||
    'none'

  const waterBucket: 'coastal' | 'inland' = COASTAL_TYPES.has(waterType) ? 'coastal' : 'inland'

  function n(v: number | null): number {
    return v !== null ? v / 100 : 0.5
  }

  return {
    areaType,
    waterBucket,
    waterType,
    norm: { scene: n(scene), race: n(race), bach: n(bach), dem: n(dem), scap: n(scap), gvi: n(gvi), water: n(water) },
    raw:  { scene, race, bach, dem, scap, gvi, water },
  }
}

function weightedDistance(a: Record<VibeKey, number>, b: Record<VibeKey, number>): number {
  let total = 0
  let wsum = 0
  for (const [k, w] of Object.entries(VIBE_WEIGHTS) as [VibeKey, number][]) {
    const diff = a[k] - b[k]
    total += w * diff * diff
    wsum += w
  }
  return Math.sqrt(total / wsum)
}

export function rankVibeTwins(
  query: CatalogMapPlace,
  candidates: CatalogMapPlace[],
  keyFn: (p: CatalogMapPlace) => string,
  limit = 12,
): VibeTwinResult[] {
  const qf = extractVibeFeatures(query)
  if (!qf.areaType) return []

  const results: VibeTwinResult[] = []
  for (const place of candidates) {
    const pf = extractVibeFeatures(place)
    if (pf.areaType !== qf.areaType) continue
    if (pf.waterBucket !== qf.waterBucket) continue

    const dist = weightedDistance(qf.norm, pf.norm)
    const matchPct = Math.max(0, Math.round((1 - dist) * 100))
    results.push({ key: keyFn(place), place, matchPct, vibeFeatures: pf, queryFeatures: qf })
  }

  results.sort((a, b) => b.matchPct - a.matchPct)
  return results.slice(0, limit)
}
