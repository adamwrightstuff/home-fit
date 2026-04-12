import { PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'

export type TwinMatchResult = {
  key: string
  place: CatalogMapPlace
  distance: number
  matchPct: number
  comparedPillars: PillarKey[]
}

/** Unchecked by default in Twin Finder (5 of 13). */
export const TWIN_PILLAR_DEFAULT_UNCHECKED: PillarKey[] = [
  'public_transit_access',
  'climate_risk',
  'air_travel_access',
  'economic_security',
  'quality_education',
]

/** Default 8 pillars on: all except TWIN_PILLAR_DEFAULT_UNCHECKED. */
export function defaultTwinPillarSet(): Set<PillarKey> {
  const unchecked = new Set(TWIN_PILLAR_DEFAULT_UNCHECKED)
  return new Set(PILLAR_ORDER.filter((k) => !unchecked.has(k)))
}

function pillarScoreOrZero(place: CatalogMapPlace, k: PillarKey): number {
  const p = place.score.livability_pillars as unknown as
    | Record<string, { score?: number; status?: string }>
    | undefined
  const row = p?.[k]
  if (!row || row.status === 'failed') return 0
  const s = row.score
  if (typeof s !== 'number' || !Number.isFinite(s)) return 0
  return s
}

/**
 * Euclidean distance over selected pillars; null/zero scores count as 0.
 * distance = sqrt( Σ (query - candidate)² ) for each selected pillar.
 */
export function twinDistance(
  query: CatalogMapPlace,
  candidate: CatalogMapPlace,
  pillars: PillarKey[]
): { distance: number; compared: PillarKey[] } {
  let sum = 0
  for (const k of pillars) {
    const a = pillarScoreOrZero(query, k)
    const b = pillarScoreOrZero(candidate, k)
    sum += (a - b) ** 2
  }
  return { distance: Math.sqrt(sum), compared: [...pillars] }
}

/** Spec: max(0, round((1 - distance / 100) * 100)). */
export function matchPctFromDistance(distance: number): number {
  return Math.max(0, Math.round((1 - distance / 100) * 100))
}

export function rankTwinMatches(
  query: CatalogMapPlace,
  candidates: CatalogMapPlace[],
  pillarKeys: PillarKey[],
  keyFn: (p: CatalogMapPlace) => string,
  limit = 12
): TwinMatchResult[] {
  if (pillarKeys.length < 2) return []
  const out: TwinMatchResult[] = []
  for (const place of candidates) {
    const { distance, compared } = twinDistance(query, place, pillarKeys)
    out.push({
      key: keyFn(place),
      place,
      distance,
      matchPct: matchPctFromDistance(distance),
      comparedPillars: compared,
    })
  }
  out.sort((a, b) => b.matchPct - a.matchPct)
  return out.slice(0, limit)
}

export function pillarDiffs(
  query: CatalogMapPlace,
  twin: CatalogMapPlace,
  pillars: PillarKey[]
): { key: PillarKey; diff: number; query: number; twin: number }[] {
  const rows: { key: PillarKey; diff: number; query: number; twin: number }[] = []
  for (const k of pillars) {
    const a = pillarScoreOrZero(query, k)
    const b = pillarScoreOrZero(twin, k)
    rows.push({ key: k, diff: b - a, query: a, twin: b })
  }
  return rows
}

/** Up to 6 pillar diff bars, largest |diff| first (typically 4–6 when enough pillars are selected). */
export function topPillarDiffsByMagnitude(
  query: CatalogMapPlace,
  twin: CatalogMapPlace,
  pillars: PillarKey[]
): { key: PillarKey; diff: number; query: number; twin: number }[] {
  const rows = pillarDiffs(query, twin, pillars)
  rows.sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff))
  return rows.slice(0, Math.min(6, rows.length))
}
