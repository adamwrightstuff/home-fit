/**
 * Server-safe helpers to merge saved score payloads (same place, add more pillars).
 * Used by POST /api/me/saved-scores to merge incoming pillars with existing so we don't lose previous pillars.
 */

import { PILLAR_ORDER } from '@/lib/pillars'

function prioritiesToTokens(priorities: Record<string, unknown> | null | undefined): Record<string, number> {
  if (!priorities || typeof priorities !== 'object') {
    const equal = 100 / PILLAR_ORDER.length
    const out: Record<string, number> = {}
    PILLAR_ORDER.forEach((k, i) => {
      out[k] = i < PILLAR_ORDER.length - 1 ? Math.trunc(equal) : 100 - Math.trunc(equal) * (PILLAR_ORDER.length - 1)
    })
    return out
  }
  const weightMap: Record<string, number> = { none: 0, low: 1, medium: 2, high: 3 }
  const weights: Record<string, number> = {}
  let totalWeight = 0
  for (const k of PILLAR_ORDER) {
    const raw = String((priorities as Record<string, unknown>)[k] ?? 'none').toLowerCase().trim()
    const w = weightMap[raw] ?? 0
    weights[k] = w
    totalWeight += w
  }
  if (totalWeight <= 0) {
    const equal = 100 / PILLAR_ORDER.length
    const out: Record<string, number> = {}
    PILLAR_ORDER.forEach((k, i) => {
      out[k] = i < PILLAR_ORDER.length - 1 ? Math.trunc(equal) : 100 - Math.trunc(equal) * (PILLAR_ORDER.length - 1)
    })
    return out
  }
  const proportional: Record<string, number> = {}
  const fractional: Array<{ k: string; frac: number; idx: number }> = []
  PILLAR_ORDER.forEach((k, idx) => {
    const w = weights[k]
    if (w > 0) {
      const p = (w / totalWeight) * 100
      proportional[k] = p
      fractional.push({ k, frac: p - Math.trunc(p), idx })
    } else {
      proportional[k] = 0
    }
  })
  const rounded: Record<string, number> = {}
  let totalRounded = 0
  for (const k of PILLAR_ORDER) {
    const v = Math.trunc(proportional[k] ?? 0)
    rounded[k] = v
    totalRounded += v
  }
  let remainder = 100 - totalRounded
  if (remainder > 0 && fractional.length) {
    fractional.sort((a, b) => (b.frac !== a.frac ? b.frac - a.frac : a.idx - b.idx))
    for (let i = 0; i < remainder; i++) {
      const pick = fractional[i]
      if (!pick) break
      rounded[pick.k] = (rounded[pick.k] ?? 0) + 1
    }
  }
  for (const k of PILLAR_ORDER) {
    rounded[k] = Number.isFinite(rounded[k]) ? rounded[k] : 0
  }
  return rounded
}

function getScoreFromPillar(pillar: unknown): number | null {
  if (pillar && typeof pillar === 'object' && typeof (pillar as { score?: number }).score === 'number') {
    const s = (pillar as { score: number }).score
    return Number.isFinite(s) ? s : null
  }
  return null
}

/**
 * Merge existing livability_pillars with incoming. Incoming overwrites per pillar.
 * Returns merged payload and total_score from merged pillars + priorities (only pillars with scores get weight).
 */
export function mergeSavedScorePayload(
  existingPayload: Record<string, unknown> | null,
  incomingPayload: Record<string, unknown>,
  priorities: Record<string, unknown>
): { mergedPayload: Record<string, unknown>; total_score: number } {
  const existingPillars = (existingPayload?.livability_pillars as Record<string, unknown>) ?? {}
  const incomingPillars = (incomingPayload?.livability_pillars as Record<string, unknown>) ?? {}
  const mergedPillars = { ...existingPillars, ...incomingPillars }

  const scores: Record<string, number> = {}
  for (const k of Object.keys(mergedPillars)) {
    const score = getScoreFromPillar(mergedPillars[k])
    if (score != null) scores[k] = score
  }
  if (Object.keys(scores).length === 0) {
    const total = typeof incomingPayload.total_score === 'number' ? incomingPayload.total_score : 0
    return {
      mergedPayload: { ...incomingPayload, livability_pillars: mergedPillars, total_score: total },
      total_score: total,
    }
  }

  // Only pillars with scores get weight; others treated as None so total = weighted sum of scored pillars only.
  const prioritiesForScoredOnly: Record<string, unknown> = {}
  for (const k of PILLAR_ORDER) {
    prioritiesForScoredOnly[k] = scores[k] != null ? (priorities as Record<string, unknown>)[k] ?? 'Medium' : 'None'
  }
  const tokens = prioritiesToTokens(prioritiesForScoredOnly)
  let weightSum = 0
  let weightedSum = 0
  for (const [k, score] of Object.entries(scores)) {
    const w = Number(tokens[k] ?? 0)
    if (w > 0) {
      weightSum += w
      weightedSum += score * w
    }
  }
  const total_score =
    weightSum > 0 ? Math.round((weightedSum / weightSum) * 100) / 100 : Object.values(scores).reduce((a, s) => a + s, 0) / Object.keys(scores).length

  const mergedPayload: Record<string, unknown> = {
    ...incomingPayload,
    livability_pillars: mergedPillars,
    total_score,
  }
  return { mergedPayload, total_score }
}
