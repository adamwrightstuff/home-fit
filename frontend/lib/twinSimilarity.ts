import { PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'

export type TwinMatchResult = {
  key: string
  place: CatalogMapPlace
  distance: number
  matchPct: number
  comparedPillars: PillarKey[]
}

/** Unchecked by default in Twin Finder. */
export const TWIN_PILLAR_DEFAULT_UNCHECKED: PillarKey[] = []

/** Default: all pillars on. */
export function defaultTwinPillarSet(): Set<PillarKey> {
  return new Set(PILLAR_ORDER)
}

function pillarScoreOrNull(place: CatalogMapPlace, k: PillarKey): number | null {
  const p = place.score.livability_pillars as unknown as
    | Record<string, { score?: number; status?: string }>
    | undefined
  const row = p?.[k]
  if (!row || row.status === 'failed' || row.status === 'no_data' || row.status === 'fallback') return null
  const s = row.score
  if (typeof s !== 'number' || !Number.isFinite(s)) return null
  return s
}

/**
 * Euclidean distance over selected pillars.
 * Pillars where either query or candidate has no data are skipped entirely
 * so missing-data gaps don't unfairly penalize candidates (e.g. SF built_beauty=null).
 * Normalization uses the count of pillars that were actually compared.
 */
export function twinDistance(
  query: CatalogMapPlace,
  candidate: CatalogMapPlace,
  pillars: PillarKey[]
): { distance: number; compared: PillarKey[] } {
  let sum = 0
  const compared: PillarKey[] = []
  for (const k of pillars) {
    const a = pillarScoreOrNull(query, k)
    const b = pillarScoreOrNull(candidate, k)
    if (a === null || b === null) continue
    sum += (a - b) ** 2
    compared.push(k)
  }
  return { distance: Math.sqrt(sum), compared }
}

/** Normalize distance by max possible (100 * sqrt(N)) so match% is meaningful with any number of pillars. */
export function matchPctFromDistance(distance: number, numPillars: number): number {
  const maxDist = 100 * Math.sqrt(Math.max(1, numPillars))
  return Math.max(0, Math.round((1 - distance / maxDist) * 100))
}

/** Extract SES band from a place's status_signal breakdown. */
export function placeSesBand(place: CatalogMapPlace): string | null {
  const archetype = (place.score as { status_signal_breakdown?: { archetype?: string } })
    ?.status_signal_breakdown?.archetype
  return archetype ?? null
}

export function rankTwinMatches(
  query: CatalogMapPlace,
  candidates: CatalogMapPlace[],
  pillarKeys: PillarKey[],
  keyFn: (p: CatalogMapPlace) => string,
  limit = 12,
  sameBandOnly = false
): TwinMatchResult[] {
  if (pillarKeys.length < 2) return []
  const queryBand = sameBandOnly ? placeSesBand(query) : null
  const out: TwinMatchResult[] = []
  for (const place of candidates) {
    if (sameBandOnly && queryBand && placeSesBand(place) !== queryBand) continue
    const { distance, compared } = twinDistance(query, place, pillarKeys)
    out.push({
      key: keyFn(place),
      place,
      distance,
      matchPct: matchPctFromDistance(distance, compared.length),
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
    const a = pillarScoreOrNull(query, k) ?? 0
    const b = pillarScoreOrNull(twin, k) ?? 0
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
