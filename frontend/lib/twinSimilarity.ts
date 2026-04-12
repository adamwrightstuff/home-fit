import { PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'

export type TwinMatchResult = {
  key: string
  place: CatalogMapPlace
  distance: number
  matchPct: number
  comparedPillars: PillarKey[]
}

function pillarScore(place: CatalogMapPlace, k: PillarKey): number | null {
  const p = place.score.livability_pillars as unknown as
    | Record<string, { score?: number; status?: string }>
    | undefined
  const row = p?.[k]
  if (!row || typeof row.score !== 'number' || !Number.isFinite(row.score)) return null
  if (row.status === 'failed') return null
  return row.score
}

/** Euclidean distance over selected pillars; skips pairs where either score missing. */
export function twinDistance(
  query: CatalogMapPlace,
  candidate: CatalogMapPlace,
  pillars: PillarKey[]
): { distance: number; compared: PillarKey[] } {
  let sum = 0
  const compared: PillarKey[] = []
  for (const k of pillars) {
    const a = pillarScore(query, k)
    const b = pillarScore(candidate, k)
    if (a == null || b == null) continue
    compared.push(k)
    sum += (a - b) ** 2
  }
  return { distance: Math.sqrt(sum), compared }
}

/** Spec: max(0, round((1 - dist/100) * 100)). */
export function matchPctFromDistance(distance: number): number {
  return Math.max(0, Math.round((1 - distance / 100) * 100))
}

export function rankTwinMatches(
  query: CatalogMapPlace,
  candidates: CatalogMapPlace[],
  pillarKeys: PillarKey[],
  keyFn: (p: CatalogMapPlace) => string
): TwinMatchResult[] {
  const out: TwinMatchResult[] = []
  for (const place of candidates) {
    const { distance, compared } = twinDistance(query, place, pillarKeys)
    if (compared.length === 0) continue
    out.push({
      key: keyFn(place),
      place,
      distance,
      matchPct: matchPctFromDistance(distance),
      comparedPillars: compared,
    })
  }
  out.sort((a, b) => a.distance - b.distance)
  return out
}

export function pillarDiffs(
  query: CatalogMapPlace,
  twin: CatalogMapPlace,
  pillars: PillarKey[]
): { key: PillarKey; diff: number; query: number; twin: number }[] {
  const rows: { key: PillarKey; diff: number; query: number; twin: number }[] = []
  for (const k of pillars) {
    const a = pillarScore(query, k)
    const b = pillarScore(twin, k)
    if (a == null || b == null) continue
    rows.push({ key: k, diff: b - a, query: a, twin: b })
  }
  return rows
}

export const DEFAULT_TWIN_PILLARS: PillarKey[] = [...PILLAR_ORDER]
