import type { ScoreResponse } from '@/types/api'
import { PILLAR_ORDER, SCORE_BANDS, type PillarKey } from '@/lib/pillars'
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

  // Include extra keys (e.g. natural_beauty, built_environment) that are in priorities but not PILLAR_ORDER.
  const allKeys: string[] = [...PILLAR_ORDER]
  for (const k of Object.keys(priorities)) {
    if (!allKeys.includes(k) && String(priorities[k] ?? 'none').toLowerCase().trim() !== 'none') {
      allKeys.push(k)
    }
  }

  const weights: Record<string, number> = {}
  const weightMap: Record<string, number> = { none: 0, low: 1, medium: 2, high: 3 }

  let totalWeight = 0
  for (const k of allKeys) {
    const raw = String(priorities[k] ?? 'none').toLowerCase().trim()
    const w = weightMap[raw] ?? 0
    weights[k] = w
    totalWeight += w
  }

  if (totalWeight <= 0) return equalAllocation(PILLAR_ORDER)

  // Largest remainder method, mirroring backend behavior (stable tie-break by original pillar order).
  const proportional: Record<string, number> = {}
  const fractional: Array<{ k: string; frac: number; idx: number }> = []
  for (let idx = 0; idx < allKeys.length; idx++) {
    const k = allKeys[idx]
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
  for (const k of allKeys) {
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

  // Ensure all standard pillars exist (extra keys already present via allKeys loop).
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

/**
 * Pillar participates in weighted HomeFit total. Execution failures (`status === 'failed'`, "?" in UI)
 * are excluded so priority weight is renormalized across pillars that actually scored — avoids "dead"
 * weight on failed rows and a headline total that feels inconsistent with visible pillar scores.
 */
function isPillarEligibleForHomeFitBlend(pillar: { score?: unknown; status?: string } | null | undefined): boolean {
  if (!pillar || typeof pillar.score !== 'number' || !Number.isFinite(pillar.score)) return false
  if (pillar.status === 'failed') return false
  return true
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

  const allocation = fallbackAllocation ?? tokenAllocation
  const eligibleKeys = Object.keys(nextPillars).filter((k) => isPillarEligibleForHomeFitBlend(nextPillars[k]))
  let allocSum = 0
  for (const k of eligibleKeys) {
    allocSum += Number(allocation[k] ?? 0)
  }

  const processedKeys = new Set<string>()
  for (const k of Object.keys(nextPillars)) {
    const pillar = nextPillars[k]
    if (!pillar || !isPillarEligibleForHomeFitBlend(pillar)) continue
    processedKeys.add(k)

    const baseW = Number(allocation[k] ?? 0)
    const weight = allocSum > 0 ? Math.round(((baseW / allocSum) * 100) * 10) / 10 : 0
    const score = Number(pillar.score ?? 0)
    const contributionRaw = allocSum > 0 ? (score * baseW) / allocSum : 0
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

  // Missing numeric score, execution failures, or stale API rows: no weight/contribution in the blend.
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

/**
 * Deal-breaker gate for housing_value: price-to-income ratio must clear the standard
 * affordability threshold (≤3x annual income — the same "Affordable (standard threshold)"
 * cutoff documented in pillars/housing_value.py's _score_local_affordability). Independent
 * of the importance weight; this only filters, never reweights.
 */
export const HOUSING_VALUE_DEALBREAKER_RATIO = 3.0

export function passesHousingValueDealbreaker(
  medianHomeValue: number | null | undefined,
  income: number | null | undefined
): boolean {
  if (!medianHomeValue || !income || income <= 0) return true
  return medianHomeValue / income <= HOUSING_VALUE_DEALBREAKER_RATIO
}

/**
 * Deal-breaker gate for air_travel_access: drive time to the nearest airport must clear
 * 60 minutes — the inflection point in pillars/air_travel_access.py's own _TIME_BANDS,
 * where scoring transitions from "good" (50min = 74pts) to visibly declining (70min =
 * 58pts), and which matches the general airport-catchment/relocation research convention
 * of 30-60 minutes as the "acceptable" range before access starts reading as a drawback.
 * 120 (the old value) was the band table's outer edge before "gentle decay," which is too
 * lenient to function as a dealbreaker in dense multi-airport metros like NYC/LA. Mirrors
 * that file's _drive_minutes (road-circuity-adjusted distance / area-type drive speed).
 */
export const AIR_TRAVEL_DEALBREAKER_MINUTES = 60
const AIRPORT_DRIVE_KMH: Record<string, number> = {
  historic_urban: 34.0, urban_residential: 40.0, suburban: 52.0,
  urban_core: 33.0, urban: 38.0, dense_suburban: 45.0,
  exurban: 65.0, rural: 72.0,
}
const ROAD_CIRCUITY = 1.3

export function passesAirTravelDealbreaker(
  nearestAirportKm: number | null | undefined,
  effectiveAreaType: string | null | undefined
): boolean {
  if (!nearestAirportKm || nearestAirportKm <= 0) return true
  const kmh = AIRPORT_DRIVE_KMH[(effectiveAreaType || '').toLowerCase()] ?? 50.0
  const minutes = (nearestAirportKm * ROAD_CIRCUITY) / kmh * 60.0
  return minutes <= AIR_TRAVEL_DEALBREAKER_MINUTES
}

/**
 * Deal-breaker gate for quality_education: pillar score must clear 60 — the "3-star
 * equivalent" tier in pillars/schools.py's rating formula (rankStars * 20, so 3/5 stars =
 * 60). The catalog stores the already-aggregated rating, not a separate percentile field,
 * so this anchors directly on score using that source system's own star-tier boundary.
 */
export const QUALITY_EDUCATION_DEALBREAKER_SCORE = 60

export function passesQualityEducationDealbreaker(score: number | null | undefined): boolean {
  if (score === null || score === undefined) return true
  return score >= QUALITY_EDUCATION_DEALBREAKER_SCORE
}

/**
 * Deal-breaker gate for neighborhood_beauty: pillar score must clear the bottom of the
 * "Fair" band in SCORE_BANDS (lib/pillars.ts) — the same score-badge boundary already shown
 * to users on every pillar card. neighborhood_beauty has no documented quality threshold of
 * its own (unlike housing_value/air_travel_access/quality_education), so this borrows the
 * one real, user-visible boundary that exists rather than inventing a number: excludes only
 * what the UI itself already labels "Low."
 */
export const NEIGHBORHOOD_BEAUTY_DEALBREAKER_SCORE =
  SCORE_BANDS.find((b) => b.label === 'Fair')?.min ?? 45

export function passesNeighborhoodBeautyDealbreaker(score: number | null | undefined): boolean {
  if (score === null || score === undefined) return true
  return score >= NEIGHBORHOOD_BEAUTY_DEALBREAKER_SCORE
}

/**
 * Deal-breaker gate for community_safety: pillar score must clear 50 — the exact midpoint
 * of pillars/community_safety.py's _z_to_slot mapping (z=0, i.e. crime rate exactly at the
 * area-type-typical baseline, maps to slot=50). Anchors to "no worse than typical for this
 * area type," the real center point of that pillar's own z-score normalization.
 */
export const COMMUNITY_SAFETY_DEALBREAKER_SCORE = 50

export function passesCommunitySafetyDealbreaker(score: number | null | undefined): boolean {
  if (score === null || score === undefined) return true
  return score >= COMMUNITY_SAFETY_DEALBREAKER_SCORE
}

/**
 * Deal-breaker gate for neighborhood_amenities: business count within walking distance must
 * clear the "adequate" tier from pillars/neighborhood_amenities.py's _score_density —
 * 15 businesses (suburban baseline), scaled +20% for urban_core (18) and -30% for
 * exurban/rural (11). Anchors to that pillar's own research-backed floor, not an invented
 * count.
 */
const AMENITIES_ADEQUATE_THRESHOLD: Record<string, number> = {
  urban_core: 18,
  exurban: 11,
  rural: 11,
}
const AMENITIES_ADEQUATE_DEFAULT = 15 // suburban baseline

export function passesNeighborhoodAmenitiesDealbreaker(
  businessesWithinWalk: number | null | undefined,
  effectiveAreaType: string | null | undefined
): boolean {
  if (businessesWithinWalk === null || businessesWithinWalk === undefined) return true
  const threshold = AMENITIES_ADEQUATE_THRESHOLD[(effectiveAreaType || '').toLowerCase()] ?? AMENITIES_ADEQUATE_DEFAULT
  return businessesWithinWalk >= threshold
}

/**
 * Deal-breaker gate for public_transit_access: mean commute time must clear 45 minutes,
 * applied uniformly regardless of area type. Unlike neighborhood_amenities (where walkable
 * business density is physically impossible to replicate at rural scale), commute tolerance
 * is a property of the person, not the area -- Marchetti's constant (transportation/urban
 * planning research) finds humans budget ~30min one-way for travel across history and
 * geography regardless of context, so the dealbreaker shouldn't grade that tolerance on an
 * area-type curve just because the pillar's own *score* does for relative-grading reasons.
 * 45 (not the research-ideal 30) accounts for mean_commute_minutes being a Census-style
 * area aggregate, not a measurement of any specific person's actual commute to their actual
 * job -- padding past the strict ideal absorbs that measurement uncertainty. A flat 30 would
 * exclude 75% of NYC and 50% of LA; 45 gives 11%/1%, in line with the other dealbreakers.
 */
const PUBLIC_TRANSIT_DEALBREAKER_MINUTES = 45

export function passesPublicTransitDealbreaker(
  meanCommuteMinutes: number | null | undefined
): boolean {
  if (meanCommuteMinutes === null || meanCommuteMinutes === undefined || meanCommuteMinutes <= 0) return true
  return meanCommuteMinutes <= PUBLIC_TRANSIT_DEALBREAKER_MINUTES
}

/** Mirror of Python _score_local_affordability — step function on price-to-income ratio (0–50 pts). */
function scoreLocalAffordability(homeValue: number, income: number): number {
  if (!homeValue || !income) return 0
  const ratio = homeValue / income
  if (ratio <= 2.0) return 50
  if (ratio <= 2.5) return 45
  if (ratio <= 3.0) return 40
  if (ratio <= 3.5) return 35
  if (ratio <= 4.0) return 30
  if (ratio <= 4.5) return 25
  if (ratio <= 5.0) return 20
  if (ratio <= 6.0) return 15
  if (ratio <= 7.0) return 10
  return 5
}

/**
 * Recompute housing_value score using a user-supplied income instead of the local median.
 * Only local_affordability (0–50 pts) changes; space and value_efficiency are income-independent.
 * Returns original data unchanged when userIncome is null/zero or median_home_value is missing.
 */
export function applyUserIncomeToScore(
  data: ScoreResponse,
  userIncome: number | null | undefined
): ScoreResponse {
  if (!userIncome || userIncome <= 0) return data
  const hv = (data.livability_pillars as any)?.housing_value
  if (!hv) return data
  const medianHomeValue = Number(hv.summary?.median_home_value ?? 0)
  if (medianHomeValue <= 0) return data
  const bk = hv.breakdown ?? {}
  const space = Number(bk.space ?? 0)
  const valueEfficiency = Number(bk.value_efficiency ?? 0)
  const newAffordability = scoreLocalAffordability(medianHomeValue, userIncome)
  const newTotal = Math.min(100, Math.max(0, newAffordability + space + valueEfficiency))
  return {
    ...data,
    livability_pillars: {
      ...data.livability_pillars,
      housing_value: {
        ...hv,
        score: newTotal,
        breakdown: { ...bk, local_affordability: newAffordability },
      },
    } as ScoreResponse['livability_pillars'],
  }
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

