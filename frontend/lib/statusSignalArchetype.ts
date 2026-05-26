import type { StatusSignalBreakdown } from '@/types/api'
import { signalStrengthFromCompositeScore } from '@/lib/statusSignalStrength'

export type NonTypicalArchetype = 'Established' | 'Affluent' | 'Transitional' | 'Working Class'

type ArchetypeVector = Record<NonTypicalArchetype, number>

export type StatusBadgeVariant = 'named' | 'leans' | 'mixed'

const FEATURE_KEYS = ['education', 'home_cost', 'occupation', 'wealth'] as const
type FeatureKey = (typeof FEATURE_KEYS)[number]

type FeatureVector = Record<FeatureKey, number>

const LEAN_MODEL_VERSION = 'catalog-v2-2026-05-04'
const LEAN_GAP_THRESHOLD_PCT = 15

// Frozen constants (derived from LA + NYC catalog outputs, 2026-05-04).
const FEATURE_MEAN: FeatureVector = {
  education: 57.5562,
  home_cost: 48.0897,
  occupation: 59.6815,
  wealth: 62.1596,
}

const FEATURE_STD: FeatureVector = {
  education: 28.6850,
  home_cost: 22.6496,
  occupation: 23.2286,
  wealth: 20.0920,
}

const ARCHETYPE_CENTROIDS: Record<NonTypicalArchetype, FeatureVector> = {
  Established: {
    education: 94.6040,
    home_cost: 62.0734,
    occupation: 90.5709,
    wealth: 81.3959,
  },
  Affluent: {
    education: 67.9290,
    home_cost: 54.5464,
    occupation: 69.4505,
    wealth: 75.0207,
  },
  Transitional: {
    education: 45.5106,
    home_cost: 71.2164,
    occupation: 46.3975,
    wealth: 41.0861,
  },
  'Working Class': {
    education: 39.0243,
    home_cost: 36.8615,
    occupation: 43.5893,
    wealth: 47.7213,
  },
}

const ARCHETYPE_ONE_LINERS: Record<NonTypicalArchetype, string> = {
  Established: 'Established, credential-rich profile. Status here is grounded in education and professional standing.',
  Affluent: 'Wealth-forward profile with income outliers. High occupation mix and rising prosperity.',
  Transitional: 'Home values materially exceed resident wealth — a neighborhood whose cost has run ahead of its income.',
  'Working Class': 'Modest status signal. Working-community character with cost that matches the economic profile.',
}

/** API archetypes from pillars/status_signal (not in lean centroid model). */
const API_ARCHETYPE_ONE_LINERS: Record<string, string> = {
  'Upper Middle Class': 'Credential and career driven — high education and white-collar mix with above-median wealth.',
  'Up-and-Coming': 'Housing market runs hot relative to typical resident wealth — a neighborhood in active transition.',
  'Immigrant Community': 'Established ethnic enclave with strong community identity, cultural roots, and long-term residents.',
  'Middle Class': 'Solid footing on income and housing — comfortable without one dominant status story.',
  Unclassified: 'Residential signal too thin to classify — treat as low confidence.',
}

/** Legacy archetype labels no longer shown — centroid model takes over for these. */
const RETIRED_ARCHETYPES = new Set(['Professional', 'Rooted'])

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
  const weights: ArchetypeVector = {
    Established: 0,
    Affluent: 0,
    Transitional: 0,
    'Working Class': 0,
  }

  for (const archetype of Object.keys(ARCHETYPE_CENTROIDS) as NonTypicalArchetype[]) {
    const d = euclideanDistance(vec, ARCHETYPE_CENTROIDS[archetype])
    weights[archetype] = 1 / (d + epsilon)
  }

  const total = Object.values(weights).reduce((acc, w) => acc + w, 0)
  if (!Number.isFinite(total) || total <= 0) return null

  return {
    Established: (100 * weights.Established) / total,
    Affluent: (100 * weights.Affluent) / total,
    Transitional: (100 * weights.Transitional) / total,
    'Working Class': (100 * weights['Working Class']) / total,
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
  return archetype || 'Unknown'
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
  const rawArchetype = breakdown?.archetype ?? null
  const archetype = rawArchetype && !RETIRED_ARCHETYPES.has(rawArchetype) ? rawArchetype : null
  const strengthLabel = getStatusSignalStrengthLabel(breakdown, compositeScore)
  const topMatch = getTopArchetypeMatch(breakdown)
  const gapPct = topMatch?.gapPct ?? null
  const suffix = strengthLabel ? ` · ${strengthLabel.replace(' signal', '')}` : ''

  if (archetype) {
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
    return {
      variant: 'leans',
      text: `Leans ${topMatch.top}${suffix}`,
      strengthLabel,
      leanArchetype: topMatch.top,
      gapPct: topMatch.gapPct,
      modelVersion: LEAN_MODEL_VERSION,
    }
  }

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
  if (archetype) {
    const text = archetypeOneLiner(archetype)
    return text ? `${archetype} places have ${text.toLowerCase()}` : null
  }
  if (badge.variant === 'leans' && badge.leanArchetype) {
    const oneLiner = archetypeOneLiner(badge.leanArchetype)
    return `This place leans closest to ${badge.leanArchetype} — ${oneLiner}`
  }
  return 'This place combines characteristics from multiple status profiles without a dominant pattern.'
}

export function archetypeOneLiner(archetype: string | null | undefined): string {
  const a = (archetype ?? '').trim()
  if (!a) return 'This place combines characteristics from multiple status profiles without a dominant pattern.'
  const legacy = ARCHETYPE_ONE_LINERS[a as NonTypicalArchetype]
  if (legacy) return legacy
  return API_ARCHETYPE_ONE_LINERS[a] ?? 'A distinct status profile for this area.'
}

export function getLeanThresholdPct(): number {
  return LEAN_GAP_THRESHOLD_PCT
}
