import type { StatusSignalBreakdown } from '@/types/api'
import { signalStrengthFromCompositeScore } from '@/lib/statusSignalStrength'

// SES bands (DFG-style composite)
export type SESBand = 'Wealthy' | 'Well-Off' | 'Middle Class' | 'Modest' | 'Working Class' | 'Struggling'

// Character overlays — applied on top of SES band when gentrification signal fires
export type CharacterOverlay = 'Up-and-Coming'

export type NonTypicalArchetype = SESBand | CharacterOverlay

type ArchetypeVector = Record<SESBand, number>

export type StatusBadgeVariant = 'named' | 'leans' | 'mixed'

const FEATURE_KEYS = ['education', 'home_cost', 'occupation', 'wealth'] as const
type FeatureKey = (typeof FEATURE_KEYS)[number]

type FeatureVector = Record<FeatureKey, number>

const LEAN_MODEL_VERSION = 'dfg-v1-2026-06'
const LEAN_GAP_THRESHOLD_PCT = 15

// Feature means/stds derived from NYC + LA metro catalog (DFG wealth score, 0-100 mapped)
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

// Centroids for SES bands — wealth score is DFG composite mapped to 0-100
// Wealthy ≥75, Well-Off ≥63, Middle Class ≥55, Modest ≥48, Working Class ≥41, Struggling <41
const ARCHETYPE_CENTROIDS: Record<SESBand, FeatureVector> = {
  Wealthy: {
    education: 92.0,
    home_cost: 72.0,
    occupation: 88.0,
    wealth: 85.0,
  },
  'Well-Off': {
    education: 76.0,
    home_cost: 60.0,
    occupation: 74.0,
    wealth: 72.0,
  },
  'Middle Class': {
    education: 58.0,
    home_cost: 50.0,
    occupation: 58.0,
    wealth: 59.0,
  },
  Modest: {
    education: 44.0,
    home_cost: 40.0,
    occupation: 44.0,
    wealth: 50.0,
  },
  'Working Class': {
    education: 32.0,
    home_cost: 32.0,
    occupation: 32.0,
    wealth: 44.0,
  },
  Struggling: {
    education: 16.0,
    home_cost: 18.0,
    occupation: 18.0,
    wealth: 32.0,
  },
}

const ARCHETYPE_ONE_LINERS: Record<SESBand, string> = {
  Wealthy: 'High income, high education, and high home values — a genuinely affluent area by any measure.',
  'Well-Off': 'Solidly upper-middle class — professional workforce, strong education, and above-average incomes.',
  'Middle Class': 'Comfortable footing — median income, educated workforce, and housing that matches.',
  Modest: 'Working-middle profile — incomes and education slightly below the metro average.',
  'Working Class': 'Lower-income community with a working-class character and modest education attainment.',
  Struggling: 'Low income, low education attainment, and limited economic opportunity.',
}

/** Character overlays — shown when gentrification signal overrides the SES band. */
const OVERLAY_ONE_LINERS: Record<CharacterOverlay, string> = {
  'Up-and-Coming': 'Housing market runs hot relative to resident wealth — a neighborhood in active transition.',
}

/** Legacy / fallback one-liners for any remaining old API archetype strings. */
const API_ARCHETYPE_ONE_LINERS: Record<string, string> = {
  ...OVERLAY_ONE_LINERS,
  Unclassified: 'Residential signal too thin to classify — treat as low confidence.',
}

/** Legacy archetype labels no longer shown — centroid model takes over for these. */
const RETIRED_ARCHETYPES = new Set<string>([])

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
  const weights = {} as ArchetypeVector
  for (const band of Object.keys(ARCHETYPE_CENTROIDS) as SESBand[]) {
    const d = euclideanDistance(vec, ARCHETYPE_CENTROIDS[band])
    weights[band] = 1 / (d + epsilon)
  }

  const total = Object.values(weights).reduce((acc, w) => acc + w, 0)
  if (!Number.isFinite(total) || total <= 0) return null

  return Object.fromEntries(
    (Object.keys(weights) as SESBand[]).map(k => [k, (100 * weights[k]) / total])
  ) as ArchetypeVector
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

const LEGACY_ARCHETYPE_DISPLAY: Record<string, string> = {
  'Established':        'Wealthy',
  'Affluent':           'Well-Off',
  'Upper Middle Class': 'Well-Off',
  'Elite':              'Wealthy',
  'Transitional':       'Up-and-Coming',
}

export function displayArchetypeLabel(archetype: string | null | undefined): string {
  if (!archetype) return 'Unknown'
  return LEGACY_ARCHETYPE_DISPLAY[archetype] ?? archetype
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
    return text ? `${archetype} neighborhoods have a ${text.toLowerCase()}` : null
  }
  if (badge.variant === 'leans' && badge.leanArchetype) {
    const oneLiner = archetypeOneLiner(badge.leanArchetype)
    return `This place leans closest to ${badge.leanArchetype} — ${oneLiner}`
  }
  return 'Every neighborhood has a social character. Archetype captures it — classifying places by how wealth and status are expressed, using income, education, occupation, and housing data.'
}

export function archetypeOneLiner(archetype: string | null | undefined): string {
  const a = (archetype ?? '').trim()
  if (!a) return 'Every neighborhood has a social character. Status Signal classifies places by how wealth and status are expressed — using income, education, occupation, and housing data.'
  const ses = ARCHETYPE_ONE_LINERS[a as SESBand]
  if (ses) return ses
  return API_ARCHETYPE_ONE_LINERS[a] ?? 'A distinct status profile for this area.'
}

export function getLeanThresholdPct(): number {
  return LEAN_GAP_THRESHOLD_PCT
}
