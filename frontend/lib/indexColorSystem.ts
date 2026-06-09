/**
 * HomeFit index → color ramp bindings (fixed).
 * HomeFit = purple, Longevity = teal, Happiness = blue, Archetype index map = coral.
 */

import type { CatalogMapIndexMode } from '@/lib/catalogMapTypes'

export type IndexRampKey = 'purple' | 'teal' | 'blue' | 'coral'

/** Status index map: hue encodes SES band; score maps to 50 / 200 / 400 bands. */
export type StatusArchetypeRampKey =
  | 'wealthy'
  | 'well_off'
  | 'middle_class'
  | 'modest'
  | 'working_class'
  | 'struggling'
  | 'transitional'  // Up-and-Coming overlay

export const STATUS_ARCHETYPE_RAMP: Record<
  StatusArchetypeRampKey,
  { 50: string; 200: string; 400: string; 600: string; 800: string }
> = {
  // Indigo — genuinely wealthy, high income + education.
  wealthy: {
    50: '#c7d2fe',
    200: '#818cf8',
    400: '#6366f1',
    600: '#4338ca',
    800: '#312e81',
  },
  // Amber — solidly upper-middle class, professional.
  well_off: {
    50: '#fffbeb',
    200: '#fcd34d',
    400: '#d97706',
    600: '#b45309',
    800: '#78350f',
  },
  // Slate — balanced middle class baseline.
  middle_class: {
    50: '#e2e8f0',
    200: '#94a3b8',
    400: '#64748b',
    600: '#475569',
    800: '#334155',
  },
  // Warm tan — modest working-middle profile.
  modest: {
    50: '#fef3c7',
    200: '#d4b483',
    400: '#a07850',
    600: '#7a5c38',
    800: '#5a4228',
  },
  // Warm stone — working-class community.
  working_class: {
    50: '#d4cfc9',
    200: '#a8a29e',
    400: '#78716c',
    600: '#57534e',
    800: '#44403c',
  },
  // Deep gray — low income, limited opportunity.
  struggling: {
    50: '#e7e5e4',
    200: '#a8a29e',
    400: '#57534e',
    600: '#44403c',
    800: '#292524',
  },
  // Teal — Up-and-Coming overlay (cost ahead of wealth).
  transitional: {
    50: '#f0fdfa',
    200: '#5eead4',
    400: '#0d9488',
    600: '#0f766e',
    800: '#115e59',
  },
}

export function normalizeStatusArchetypeKey(archetype: string | null | undefined): StatusArchetypeRampKey {
  const a = (archetype ?? '').trim()
  if (a === 'Wealthy') return 'wealthy'
  if (a === 'Well-Off') return 'well_off'
  if (a === 'Middle Class') return 'middle_class'
  if (a === 'Modest') return 'modest'
  if (a === 'Working Class' || a === 'Immigrant Community') return 'working_class'
  if (a === 'Struggling') return 'struggling'
  if (a === 'Up-and-Coming' || a === 'Transitional') return 'transitional'
  // Legacy fallbacks
  if (a === 'Established') return 'wealthy'
  if (a === 'Affluent' || a === 'Upper Middle Class') return 'well_off'
  return 'working_class'
}

export const RAMP_HEX: Record<IndexRampKey, { 50: string; 200: string; 400: string; 600: string; 800: string }> = {
  purple: {
    50: '#EEEDFE',
    200: '#AFA9EC',
    400: '#7F77DD',
    600: '#534AB7',
    800: '#3C3489',
  },
  teal: {
    50: '#E1F5EE',
    200: '#5DCAA5',
    400: '#1D9E75',
    600: '#0F6E56',
    800: '#085041',
  },
  blue: {
    50: '#E6F1FB',
    200: '#85B7EB',
    400: '#378ADD',
    600: '#185FA5',
    800: '#0C447C',
  },
  coral: {
    50: '#FAECE7',
    200: '#F0997B',
    400: '#D85A30',
    600: '#993C1D',
    800: '#712B13',
  },
}

export function catalogModeToRamp(mode: CatalogMapIndexMode): IndexRampKey {
  switch (mode) {
    case 'homefit':
      return 'purple'
    case 'longevity':
      return 'teal'
    case 'happiness':
      return 'blue'
    case 'status':
      return 'coral'
    default:
      return 'purple'
  }
}

export function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '')
  const n = parseInt(h, 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r},${g},${b},${alpha})`
}

/** Map bubble / badge fill by score band (0–100). */
export function scoreBandFill(ramp: IndexRampKey, score: number): string {
  const s = Math.max(0, Math.min(100, score))
  const r = RAMP_HEX[ramp]
  if (s < 50) return r[50]
  if (s < 75) return r[200]
  return r[400]
}

/** Status index map: score band within the archetype hue ramp (same thresholds as scoreBandFill). */
export function scoreBandFillStatusArchetype(archetype: string | null | undefined, score: number): string {
  const key = normalizeStatusArchetypeKey(archetype)
  const r = STATUS_ARCHETYPE_RAMP[key]
  const s = Math.max(0, Math.min(100, score))
  if (s < 50) return r[50]
  if (s < 75) return r[200]
  return r[400]
}

/** Map bubble stroke for Status mode (ramp-600 @ high alpha so hue reads on 1–2px strokes). */
export function mapBubbleStrokeStatusArchetype(archetype: string | null | undefined): string {
  const key = normalizeStatusArchetypeKey(archetype)
  return hexToRgba(STATUS_ARCHETYPE_RAMP[key][600], 0.88)
}

/** Numeric color for Archetype map tab / labels when archetype is known. */
export function statusArchetypeNumeral600(archetype: string | null | undefined): string {
  const key = normalizeStatusArchetypeKey(archetype)
  return STATUS_ARCHETYPE_RAMP[key][600]
}

/** Active / underline emphasis for Archetype map tab (ramp-400, archetype-specific). */
export function statusArchetypeNumeral400(archetype: string | null | undefined): string {
  const key = normalizeStatusArchetypeKey(archetype)
  return STATUS_ARCHETYPE_RAMP[key][400]
}

/** Text on colored fill (badges, high band on dark fill). */
export function scoreBandTextOnFill(ramp: IndexRampKey, score: number): string {
  const s = Math.max(0, Math.min(100, score))
  const r = RAMP_HEX[ramp]
  if (s < 50) return r[600]
  if (s < 75) return r[800]
  return r[50]
}

/** Score numeral on white / light background (readable). */
export function scoreNumeralOnLight(ramp: IndexRampKey, score: number): string {
  const s = Math.max(0, Math.min(100, score))
  const r = RAMP_HEX[ramp]
  if (s < 50) return r[600]
  if (s < 75) return r[800]
  return r[400]
}

/** Fixed ramp-600 for index score numerals in tab cards / headers when banding not used. */
export function indexNumeral600(ramp: IndexRampKey): string {
  return RAMP_HEX[ramp][600]
}

/** Catalog map bubble stroke: ramp-600 @ 60% opacity. */
export function mapBubbleStroke(ramp: IndexRampKey): string {
  return hexToRgba(RAMP_HEX[ramp][600], 0.6)
}

/** Full breakdown CTA: fill ramp-400, text ramp-50. */
export function fullBreakdownCtaStyle(ramp: IndexRampKey): { background: string; color: string } {
  const r = RAMP_HEX[ramp]
  return { background: r[400], color: r[50] }
}

/** Active catalog tab pill (header): fill ramp-400, text ramp-50. */
export function catalogTabActiveStyle(ramp: IndexRampKey): { background: string; color: string } {
  const r = RAMP_HEX[ramp]
  return { background: r[400], color: r[50] }
}

/** Pillar weight / importance bar (HomeFit context): band fill by pillar score. */
export function homefitPillarBarFill(score: number): string {
  return scoreBandFill('purple', score)
}
