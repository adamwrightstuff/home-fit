import type { CatalogMapPlace } from '@/lib/catalogMapTypes'

/**
 * Per-pillar fields that dominate the catalog payload (about 70% of it) and that only the
 * single-place detail views read. The list, map, filters and twin/vibe matching read the paths
 * kept below; everything else on a pillar (score, summary, status, ...) is passed through as is.
 */
const HEAVY_PILLAR_KEYS = ['breakdown', 'details', 'data_quality', 'v9_breakdown'] as const

/** Heavy-key sub-paths the list-level code still needs, by pillar. */
const KEEP_PATHS: Record<string, string[][]> = {
  // Explorer reweighting (applyScenerySubPreferencesToScore) reads these; without them the list
  // shows an unadjusted score and the on-click detail swap makes it jump.
  active_outdoors: [
    ['breakdown', 'daily_urban_outdoors'],
    ['breakdown', 'wild_adventure'],
    ['breakdown', 'waterfront_lifestyle'],
    ['breakdown', 'waterfront_breakdown', 'ocean_beach'],
    ['breakdown', 'waterfront_breakdown', 'lake_river'],
    ['breakdown', 'waterfront_breakdown', 'bay_harbor'],
    ['breakdown', 'waterfront_breakdown', 'waterfront_access'],
  ],
  // School type and grade filters (applyExplorerScoreAdjustments) rescore from these.
  quality_education: [
    ['breakdown', 'split'],
    ['breakdown', 'levels'],
    ['breakdown', 'early_ed_bonus'],
    ['breakdown', 'access_bonus'],
  ],
  housing_value: [['breakdown', 'space'], ['breakdown', 'value_efficiency']],
  political_lean: [['breakdown', 'lean_2024'], ['breakdown', 'dem_pct_2024']],
  social_fabric: [['breakdown', 'social_capital']],
  natural_beauty: [
    ['v9_breakdown', 'gvi_score'],
    ['v9_breakdown', 'canopy_score'],
    ['v9_breakdown', 'topo_score'],
    ['v9_breakdown', 'landcover_score'],
    ['v9_breakdown', 'bio_score'],
    ['v9_breakdown', 'inputs', 'gvi_pct'],
    ['v9_breakdown', 'inputs', 'canopy_pct'],
    ['v9_breakdown', 'water_score'],
    ['v9_breakdown', 'water_type'],
    ['v9_breakdown', 'inputs', 'water_type'],
  ],
}

/** The disabled-pillar check in the list view reads these two data_quality flags. */
const KEEP_DATA_QUALITY = ['fallback_used', 'reason', 'degraded'] as const

function pick(src: unknown, path: string[]): unknown {
  let cur: unknown = src
  for (const k of path) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[k]
  }
  return cur
}

function assign(dst: Record<string, unknown>, path: string[], value: unknown) {
  let cur = dst
  for (const k of path.slice(0, -1)) {
    const next = cur[k]
    cur = (cur[k] = next && typeof next === 'object' ? next : {}) as Record<string, unknown>
  }
  cur[path[path.length - 1]] = value
}

function slimPillar(key: string, pillar: unknown): unknown {
  if (!pillar || typeof pillar !== 'object') return pillar
  const src = pillar as Record<string, unknown>
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(src)) {
    if (!(HEAVY_PILLAR_KEYS as readonly string[]).includes(k)) out[k] = v
  }
  const dq = src.data_quality as Record<string, unknown> | undefined
  if (dq && typeof dq === 'object') {
    out.data_quality = Object.fromEntries(KEEP_DATA_QUALITY.filter((k) => k in dq).map((k) => [k, dq[k]]))
  }
  for (const path of KEEP_PATHS[key] ?? []) {
    const v = pick(src, path)
    if (v !== undefined) assign(out, path, v)
  }
  return out
}

/** List-sized copy of a catalog place: same shape, heavy per-pillar detail dropped. */
export function slimPlace<T extends CatalogMapPlace>(place: T): T {
  const score = place.score as unknown as Record<string, unknown>
  const pillars = score?.livability_pillars as Record<string, unknown> | undefined
  if (!pillars) return place
  const slimPillars = Object.fromEntries(Object.entries(pillars).map(([k, v]) => [k, slimPillar(k, v)]))
  return { ...place, score: { ...score, livability_pillars: slimPillars } as unknown as T['score'] }
}
