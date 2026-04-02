import type { ScoreResponse } from '@/types/api'
import { PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { PillarPriorities } from '@/components/SearchOptions'

type PriorityLevel = 'None' | 'Low' | 'Medium' | 'High'

function equalAllocation(pillars: PillarKey[]): Record<string, number> {
  const out: Record<string, number> = {}
  const equal = 100 / pillars.length
  let remainder = 100
  for (let i = 0; i < pillars.length; i++) {
    const k = pillars[i]
    if (i < pillars.length - 1) {
      const tokens = Math.trunc(equal)
      out[k] = tokens
      remainder -= tokens
    } else {
      out[k] = remainder
    }
  }
  return out
}

function prioritiesToTokens(priorities: Partial<Record<string, string>> | null | undefined): Record<string, number> {
  if (!priorities) return equalAllocation(PILLAR_ORDER)

  const weights: Record<string, number> = {}
  const weightMap: Record<string, number> = { none: 0, low: 1, medium: 2, high: 3 }

  let totalWeight = 0
  for (const k of PILLAR_ORDER) {
    const raw = String(priorities[k] ?? 'none').toLowerCase().trim()
    const w = weightMap[raw] ?? 0
    weights[k] = w
    totalWeight += w
  }

  if (totalWeight <= 0) return equalAllocation(PILLAR_ORDER)

  // Largest remainder method, mirroring backend behavior (stable tie-break by original pillar order).
  const proportional: Record<string, number> = {}
  const fractional: Array<{ k: string; frac: number; idx: number }> = []
  for (let idx = 0; idx < PILLAR_ORDER.length; idx++) {
    const k = PILLAR_ORDER[idx]
    const w = weights[k]
    if (w > 0) {
      const p = (w / totalWeight) * 100
      proportional[k] = p
      fractional.push({ k, frac: p - Math.trunc(p), idx })
    } else {
      proportional[k] = 0
    }
  }

  const rounded: Record<string, number> = {}
  let totalRounded = 0
  for (const k of PILLAR_ORDER) {
    const v = Math.trunc(proportional[k] ?? 0)
    rounded[k] = v
    totalRounded += v
  }

  let remainder = 100 - totalRounded
  if (remainder > 0 && fractional.length) {
    fractional.sort((a, b) => {
      if (b.frac !== a.frac) return b.frac - a.frac
      return a.idx - b.idx
    })
    for (let i = 0; i < remainder; i++) {
      const pick = fractional[i]
      if (!pick) break
      rounded[pick.k] = (rounded[pick.k] ?? 0) + 1
    }
  }

  // Ensure all pillars exist.
  for (const k of PILLAR_ORDER) rounded[k] = Number.isFinite(rounded[k]) ? rounded[k] : 0
  return rounded
}

function isSchoolsDisabledFromResult(data: ScoreResponse): boolean {
  const qe = (data.livability_pillars as any)?.quality_education
  const fallbackUsed = qe?.data_quality?.fallback_used === true
  const reason = String(qe?.data_quality?.reason || '').toLowerCase()
  return fallbackUsed && reason.includes('disabled')
}

function applySchoolsDisabledOverride(tokenAllocation: Record<string, number | undefined>): Record<string, number> {
  const out: Record<string, number> = { ...tokenAllocation }
  out.quality_education = 0

  let remaining = 0
  for (const k of Object.keys(out)) {
    if (k === 'quality_education') continue
    const v = Number(out[k] ?? 0)
    if (Number.isFinite(v)) remaining += v
  }
  if (remaining <= 0) return out

  const scale = 100 / remaining
  for (const k of Object.keys(out)) {
    if (k === 'quality_education') continue
    out[k] = Number(out[k] ?? 0) * scale
  }

  return out
}

export function reweightScoreResponseFromPriorities(
  data: ScoreResponse,
  priorities: Record<string, PriorityLevel> | PillarPriorities
): ScoreResponse {
  const tokenAllocationInt = prioritiesToTokens(priorities as Partial<Record<string, string>>)
  const tokenAllocation = isSchoolsDisabledFromResult(data)
    ? applySchoolsDisabledOverride(tokenAllocationInt)
    : tokenAllocationInt

  const nextPillars: any = { ...data.livability_pillars }
  /** Sum of per-pillar rounded contributions so headline total matches card rows (avoids 49.1 vs 50.1-style drift). */
  let totalFromRoundedContributions = 0

  // If any pillar with a score gets weight 0 from tokenAllocation, we need a fallback so we don't show 0%.
  // Build fallback by merging user priorities with payload importance_level only for pillars that would be 0,
  // so the total always reflects the user's current preferences.
  const payloadKeys = Object.keys(nextPillars).filter(
    (k) => nextPillars[k] && typeof nextPillars[k].score === 'number'
  )
  // Use fallback only when a pillar with a score has 0 weight but the user did NOT set it to None (e.g. key mismatch).
  // When the user explicitly set a pillar to None, use tokenAllocation so that pillar gets 0% and the total is correct.
  const anyZeroWeightNeedingFallback = payloadKeys.some(
    (k) => Number(tokenAllocation[k] ?? 0) === 0 && String((priorities as Record<string, string>)[k] ?? 'none').toLowerCase().trim() !== 'none'
  )
  const fallbackAllocation =
    anyZeroWeightNeedingFallback && payloadKeys.length > 0
      ? (() => {
          const userPriorities = priorities as Partial<Record<string, string>>
          const merged: Record<string, string> = {}
          for (const k of PILLAR_ORDER) {
            const userLevel = String(userPriorities[k] ?? 'none').toLowerCase().trim()
            const hasScore = payloadKeys.includes(k)
            if (hasScore && (userLevel === 'none' || userLevel === '')) {
              const fromPayload = (nextPillars[k] as any)?.importance_level
              const s = String(fromPayload ?? 'Medium').trim()
              merged[k] = s === 'Low' || s === 'Medium' || s === 'High' ? s : 'Medium'
            } else {
              merged[k] = userLevel === 'low' || userLevel === 'medium' || userLevel === 'high'
                ? (userPriorities[k] ?? 'Medium')
                : userLevel === 'none'
                  ? 'none'
                  : 'Medium'
            }
          }
          const alloc = prioritiesToTokens(merged)
          return isSchoolsDisabledFromResult(data) ? applySchoolsDisabledOverride(alloc) : alloc
        })()
      : null

  const processedKeys = new Set<string>()
  for (const k of Object.keys(nextPillars)) {
    const pillar = nextPillars[k]
    if (!pillar || typeof pillar.score !== 'number') continue
    processedKeys.add(k)

    // Use a single allocation for all pillars so weights always sum to 100.
    const allocation = fallbackAllocation ?? tokenAllocation
    const weight = Number(allocation[k] ?? 0)
    const score = Number(pillar.score ?? 0)
    const contributionRaw = (score * weight) / 100
    const contribution = Math.round(contributionRaw * 100) / 100
    totalFromRoundedContributions += contribution

    // Normalize priority label casing to backend style.
    const p = String((priorities as any)?.[k] ?? pillar.importance_level ?? 'None')
    const importanceLevel = p === 'Low' || p === 'Medium' || p === 'High' ? p : 'None'

    nextPillars[k] = {
      ...pillar,
      weight,
      contribution,
      importance_level: importanceLevel,
    }
  }

  // Pillars without a numeric score (failed / pending) must not keep stale API weight & contribution,
  // or the sum of card contributions won't match total_score.
  for (const k of Object.keys(nextPillars)) {
    if (processedKeys.has(k)) continue
    const pillar = nextPillars[k]
    if (!pillar) continue
    nextPillars[k] = {
      ...pillar,
      weight: 0,
      contribution: 0,
    }
  }

  const nextTotal = Math.round(totalFromRoundedContributions * 100) / 100
  const finalTokenAllocation = fallbackAllocation ?? tokenAllocation

  return {
    ...data,
    livability_pillars: nextPillars,
    total_score: nextTotal,
    token_allocation: finalTokenAllocation as Record<string, number>,
    allocation_type: 'priority_based',
  }
}

/**
 * Running total from partial pillar scores (tap-to-score flow).
 * Uses only completed pillars with valid scores (excludes failed runs) and renormalizes their weights to sum to 100.
 */
export function totalFromPartialPillarScores(
  partialScores: Record<string, number | { score: number; failed?: boolean }>,
  priorities: Partial<Record<string, string>> | PillarPriorities | null | undefined
): number | null {
  const completed = Object.entries(partialScores).filter(([_, s]) => {
    if (typeof s === 'number') return Number.isFinite(s)
    if (s && typeof s === 'object' && typeof s.score === 'number') return !(s as { failed?: boolean }).failed
    return false
  }) as [string, number][]
  const scores: Record<string, number> = {}
  for (const [k, s] of completed) {
    scores[k] = typeof s === 'number' ? s : (s as { score: number }).score
  }
  if (Object.keys(scores).length === 0) return null
  const tokens = prioritiesToTokens(priorities as Partial<Record<string, string>> | null | undefined)
  let weightSum = 0
  let weightedSum = 0
  for (const [k, score] of Object.entries(scores)) {
    const w = Number(tokens[k] ?? 0)
    if (w > 0) {
      weightSum += w
      weightedSum += score * w
    }
  }
  if (weightSum <= 0) {
    return Object.values(scores).reduce((a, s) => a + s, 0) / Object.keys(scores).length
  }
  return Math.round((weightedSum / weightSum) * 100) / 100
}

/** Expose token allocation for UI: weight % per pillar from current priorities (no API). */
export function getPillarWeightsFromPriorities(
  priorities: Partial<Record<string, string>> | PillarPriorities | null | undefined
): Record<string, number> {
  return prioritiesToTokens(priorities as Partial<Record<string, string>> | null | undefined)
}

/** Per-pillar weight % and contribution from scores + priorities (recalculation without API). Excludes failed pillars. */
export function getPillarWeightsAndContributions(
  partialScores: Record<string, number | { score: number; failed?: boolean }>,
  priorities: Partial<Record<string, string>> | PillarPriorities | null | undefined
): Record<string, { weight: number; contribution: number }> {
  const tokens = prioritiesToTokens(priorities as Partial<Record<string, string>> | null | undefined)
  const completed = Object.entries(partialScores).filter(([_, s]) => {
    if (typeof s === 'number') return Number.isFinite(s)
    if (s && typeof s === 'object' && typeof s.score === 'number') return !(s as { failed?: boolean }).failed
    return false
  }) as [string, number][]
  const scores: Record<string, number> = {}
  for (const [k, s] of completed) {
    scores[k] = typeof s === 'number' ? s : (s as { score: number }).score
  }
  let weightSum = 0
  for (const [k] of completed) {
    weightSum += Number(tokens[k] ?? 0)
  }
  const scale = weightSum > 0 ? 100 / weightSum : 0
  const out: Record<string, { weight: number; contribution: number }> = {}
  for (const [k, score] of Object.entries(scores)) {
    const w = Number(tokens[k] ?? 0)
    const weight = weightSum > 0 ? Math.round(w * scale * 10) / 10 : 0
    const contribution = weightSum > 0 ? Math.round((score * (w * scale)) / 100 * 100) / 100 : 0
    out[k] = { weight, contribution }
  }
  return out
}

