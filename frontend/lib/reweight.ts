import type { ScoreResponse } from '@/types/api'
import type { PillarKey } from '@/lib/pillars'
import type { PillarPriorities } from '@/components/SearchOptions'

type PriorityLevel = 'None' | 'Low' | 'Medium' | 'High'

const PILLAR_ORDER: PillarKey[] = [
  'active_outdoors',
  'built_beauty',
  'natural_beauty',
  'neighborhood_amenities',
  'air_travel_access',
  'public_transit_access',
  'healthcare_access',
  'economic_security',
  'quality_education',
  'housing_value',
]

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
  let total = 0

  for (const k of Object.keys(nextPillars)) {
    const pillar = nextPillars[k]
    if (!pillar || typeof pillar.score !== 'number') continue

    const weight = Number(tokenAllocation[k] ?? 0)
    const score = Number(pillar.score ?? 0)
    const contribution = (score * weight) / 100
    total += contribution

    // Normalize priority label casing to backend style.
    const p = String((priorities as any)?.[k] ?? 'None')
    const importanceLevel = p === 'Low' || p === 'Medium' || p === 'High' ? p : 'None'

    nextPillars[k] = {
      ...pillar,
      weight,
      contribution: Math.round(contribution * 100) / 100,
      importance_level: importanceLevel,
    }
  }

  const nextTotal = Math.round(total * 100) / 100

  return {
    ...data,
    livability_pillars: nextPillars,
    total_score: nextTotal,
    token_allocation: tokenAllocation as Record<string, number>,
    allocation_type: 'priority_based',
  }
}

/**
 * Running total from partial pillar scores (tap-to-score flow).
 * Uses only completed pillars and renormalizes their weights to sum to 100.
 */
export function totalFromPartialPillarScores(
  partialScores: Record<string, number>,
  priorities: Partial<Record<string, string>> | PillarPriorities | null | undefined
): number | null {
  const completed = Object.entries(partialScores).filter(
    ([_, s]) => typeof s === 'number' && Number.isFinite(s)
  ) as [string, number][]
  if (completed.length === 0) return null
  const tokens = prioritiesToTokens(priorities as Partial<Record<string, string>> | null | undefined)
  let weightSum = 0
  let weightedSum = 0
  for (const [k, score] of completed) {
    const w = Number(tokens[k] ?? 0)
    if (w > 0) {
      weightSum += w
      weightedSum += score * w
    }
  }
  if (weightSum <= 0) {
    return completed.reduce((a, [, s]) => a + s, 0) / completed.length
  }
  return Math.round((weightedSum / weightSum) * 100) / 100
}

