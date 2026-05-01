import type { StatusSignalBreakdown } from '@/types/api'
import { signalStrengthFromCompositeScore } from '@/lib/statusSignalStrength'

export type NonTypicalArchetype = 'Patrician' | 'Parvenu' | 'Poseur' | 'Plebeian'

type ArchetypeVector = Record<NonTypicalArchetype, number>

export type StatusBadgeVariant = 'named' | 'leans' | 'mixed'

const FEATURE_KEYS = ['education', 'home_cost', 'occupation', 'luxury', 'wealth'] as const
type FeatureKey = (typeof FEATURE_KEYS)[number]

type FeatureVector = Record<FeatureKey, number>

const LEAN_MODEL_VERSION = 'catalog-v1-2026-05-01'
const LEAN_GAP_THRESHOLD_PCT = 15

// Frozen constants (derived from catalog outputs).
const FEATURE_MEAN: FeatureVector = {
  education: 57.55622262773723,
  home_cost: 48.139395944114476,
  occupation: 59.659468564234295,
  luxury: 10.355474452554745,
  wealth: 62.155540522257866,
}

const FEATURE_STD: FeatureVector = {
  education: 28.737486563804406,
  home_cost: 22.67606341768521,
  occupation: 23.268180023657305,
  luxury: 9.618613058717854,
  wealth: 20.128684012767327,
}

const ARCHETYPE_CENTROIDS: Record<NonTypicalArchetype, FeatureVector> = {
  Patrician: {
    education: 91.3899033816425,
    home_cost: 57.943389250837846,
    occupation: 89.21968009387756,
    luxury: 5.565217391304348,
    wealth: 79.34551606965606,
  },
  Parvenu: {
    education: 73.33890109890108,
    home_cost: 59.49501389976518,
    occupation: 72.90300477752702,
    luxury: 11.23846153846154,
    wealth: 78.0076233629957,
  },
  Poseur: {
    education: 54.52333333333333,
    home_cost: 89.00615999554118,
    occupation: 47.061183318121756,
    luxury: 13.35,
    wealth: 50.43502540370044,
  },
  Plebeian: {
    education: 16.432696476964765,
    home_cost: 28.38130438234037,
    occupation: 26.824732911967285,
    luxury: 7.16829268292683,
    wealth: 35.114857367615535,
  },
}

const ARCHETYPE_ONE_LINERS: Record<NonTypicalArchetype, string> = {
  Patrician: 'Established, credential-rich, old-money character. Status here is quiet and durable.',
  Parvenu: 'Rising status profile. Wealth and aspiration are present but the place is still becoming.',
  Poseur: 'High cost relative to underlying wealth. The address costs more than the profile suggests.',
  Plebeian: 'Modest status signal. Working character, lower cost relative to metro baseline.',
}

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

function classifierInputVector(breakdown?: StatusSignalBreakdown | null): FeatureVector | null {
  if (!breakdown || typeof breakdown !== 'object') return null
  const raw = (breakdown as { classifier_inputs?: Record<string, unknown> }).classifier_inputs
  if (!raw || typeof raw !== 'object') return null
  const vec: Partial<FeatureVector> = {}
  for (const key of FEATURE_KEYS) {
    const v = asFiniteNumber(raw[key])
    if (v == null) return null
    vec[key] = v
  }
  return vec as FeatureVector
}

function zScore(value: number, key: FeatureKey): number {
  const std = FEATURE_STD[key]
  if (!Number.isFinite(std) || std === 0) return 0
  return (value - FEATURE_MEAN[key]) / std
}

function euclideanDistance(a: FeatureVector, b: FeatureVector): number {
  let sum = 0
  for (const key of FEATURE_KEYS) {
    const da = zScore(a[key], key)
    const db = zScore(b[key], key)
    const d = da - db
    sum += d * d
  }
  return Math.sqrt(sum)
}

export function getStatusSignalStrengthLabel(
  breakdown?: StatusSignalBreakdown | null,
  compositeScore?: number | null
): string | null {
  if (typeof breakdown?.signal_strength_label === 'string' && breakdown.signal_strength_label.trim()) {
    return breakdown.signal_strength_label
  }
  if (typeof compositeScore === 'number' && Number.isFinite(compositeScore)) {
    return signalStrengthFromCompositeScore(compositeScore).label
  }
  return null
}

export function computeArchetypeMatchPercentages(
  breakdown?: StatusSignalBreakdown | null
): ArchetypeVector | null {
  const vec = classifierInputVector(breakdown)
  if (!vec) return null

  const epsilon = 1e-9
  const weights: Record<NonTypicalArchetype, number> = {
    Patrician: 0,
    Parvenu: 0,
    Poseur: 0,
    Plebeian: 0,
  }

  for (const archetype of Object.keys(ARCHETYPE_CENTROIDS) as NonTypicalArchetype[]) {
    const d = euclideanDistance(vec, ARCHETYPE_CENTROIDS[archetype])
    weights[archetype] = 1 / (d + epsilon)
  }

  const total = Object.values(weights).reduce((acc, w) => acc + w, 0)
  if (!Number.isFinite(total) || total <= 0) return null

  return {
    Patrician: (100 * weights.Patrician) / total,
    Parvenu: (100 * weights.Parvenu) / total,
    Poseur: (100 * weights.Poseur) / total,
    Plebeian: (100 * weights.Plebeian) / total,
  }
}

export function getTopArchetypeMatch(
  breakdown?: StatusSignalBreakdown | null
): { top: NonTypicalArchetype; second: NonTypicalArchetype; gapPct: number; matches: ArchetypeVector } | null {
  const matches = computeArchetypeMatchPercentages(breakdown)
  if (!matches) return null

  const ranked = (Object.entries(matches) as Array<[NonTypicalArchetype, number]>).sort((a, b) => b[1] - a[1])
  if (ranked.length < 2) return null
  const [top, second] = ranked
  return {
    top: top[0],
    second: second[0],
    gapPct: top[1] - second[1],
    matches,
  }
}

export function displayArchetypeLabel(archetype: string | null | undefined): string {
  return archetype === 'Typical' ? 'Mixed profile' : archetype || 'Mixed profile'
}

export function getStatusBadgeModel(
  breakdown?: StatusSignalBreakdown | null,
  compositeScore?: number | null
): {
  variant: StatusBadgeVariant
  text: string
  strengthLabel: string | null
  leanArchetype: NonTypicalArchetype | null
  gapPct: number | null
  modelVersion: string
} {
  const archetype = breakdown?.archetype ?? null
  const strengthLabel = getStatusSignalStrengthLabel(breakdown, compositeScore)
  const topMatch = getTopArchetypeMatch(breakdown)
  const gapPct = topMatch?.gapPct ?? null

  if (archetype && archetype !== 'Typical') {
    const suffix = strengthLabel ? ` · ${strengthLabel.replace(' signal', '')}` : ''
    return {
      variant: 'named',
      text: `${archetype}${suffix}`,
      strengthLabel,
      leanArchetype: null,
      gapPct,
      modelVersion: LEAN_MODEL_VERSION,
    }
  }

  if (topMatch && topMatch.gapPct >= LEAN_GAP_THRESHOLD_PCT) {
    const suffix = strengthLabel ? ` · ${strengthLabel.replace(' signal', '')}` : ''
    return {
      variant: 'leans',
      text: `Leans ${topMatch.top}${suffix}`,
      strengthLabel,
      leanArchetype: topMatch.top,
      gapPct: topMatch.gapPct,
      modelVersion: LEAN_MODEL_VERSION,
    }
  }

  const suffix = strengthLabel ? ` · ${strengthLabel.replace(' signal', '')}` : ''
  return {
    variant: 'mixed',
    text: `Mixed profile${suffix}`,
    strengthLabel,
    leanArchetype: topMatch?.top ?? null,
    gapPct,
    modelVersion: LEAN_MODEL_VERSION,
  }
}

export function statusTooltipCopy(
  breakdown?: StatusSignalBreakdown | null,
  compositeScore?: number | null
): string | null {
  const badge = getStatusBadgeModel(breakdown, compositeScore)
  const archetype = breakdown?.archetype ?? null
  if (archetype && archetype !== 'Typical') {
    const text = ARCHETYPE_ONE_LINERS[archetype as NonTypicalArchetype]
    return text ? `${archetype} places have ${text.toLowerCase()}` : null
  }
  if (badge.variant === 'leans' && badge.leanArchetype) {
    const oneLiner = ARCHETYPE_ONE_LINERS[badge.leanArchetype]
    return `This place has a strong status signal but doesn't fit one profile cleanly. It leans closest to ${badge.leanArchetype} - ${oneLiner}`
  }
  return 'This place combines characteristics from multiple status profiles without a dominant pattern - often reflects a neighborhood in transition or unusual economic layering.'
}

export function archetypeOneLiner(archetype: NonTypicalArchetype): string {
  return ARCHETYPE_ONE_LINERS[archetype]
}

export function getLeanThresholdPct(): number {
  return LEAN_GAP_THRESHOLD_PCT
}

