/**
 * HomeFit index → color ramp bindings (fixed).
 * HomeFit = purple, Longevity = teal, Happiness = blue, Status Signal = coral.
 */

import type { CatalogMapIndexMode } from '@/lib/catalogMapTypes'

export type IndexRampKey = 'purple' | 'teal' | 'blue' | 'coral'

/** Status Signal: hue encodes archetype; score maps to 50 / 200 / 400 bands (same as other indices). */
export type StatusArchetypeRampKey = 'patrician' | 'parvenu' | 'poseur' | 'plebeian' | 'typical'

export const STATUS_ARCHETYPE_RAMP: Record<
  StatusArchetypeRampKey,
  { 50: string; 200: string; 400: string; 600: string; 800: string }
> = {
  // Indigo/navy — distinct from Plebeian (stone gray) and Typical (coral). Older Patrician used slate = same hex as Plebeian at several bands.
  patrician: {
    50: '#eef2ff',
    200: '#a5b4fc',
    400: '#6366f1',
    600: '#4338ca',
    800: '#312e81',
  },
  parvenu: {
    50: '#fffbeb',
    200: '#fcd34d',
    400: '#d97706',
    600: '#b45309',
    800: '#78350f',
  },
  poseur: {
    50: '#f0fdfa',
    200: '#5eead4',
    400: '#0d9488',
    600: '#0f766e',
    800: '#115e59',
  },
  // Stone/neutral gray-brown — reads “plain” vs Patrician’s blue-violet.
  plebeian: {
    50: '#fafaf9',
    200: '#d6d3d1',
    400: '#78716c',
    600: '#57534e',
    800: '#44403c',
  },
  typical: {
    50: '#FAECE7',
    200: '#F0997B',
    400: '#D85A30',
    600: '#993C1D',
    800: '#712B13',
  },
}

export function normalizeStatusArchetypeKey(archetype: string | null | undefined): StatusArchetypeRampKey {
  const a = (archetype ?? '').trim()
  if (a === 'Patrician') return 'patrician'
  if (a === 'Parvenu') return 'parvenu'
  if (a === 'Poseur') return 'poseur'
  if (a === 'Plebeian') return 'plebeian'
  return 'typical'
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

/** Status Signal: score band within the archetype hue ramp (same thresholds as scoreBandFill). */
export function scoreBandFillStatusArchetype(archetype: string | null | undefined, score: number): string {
  const key = normalizeStatusArchetypeKey(archetype)
  const r = STATUS_ARCHETYPE_RAMP[key]
  const s = Math.max(0, Math.min(100, score))
  if (s < 50) return r[50]
  if (s < 75) return r[200]
  return r[400]
}

/** Map bubble stroke for Status mode (ramp-600 @ 60%), per archetype. */
export function mapBubbleStrokeStatusArchetype(archetype: string | null | undefined): string {
  const key = normalizeStatusArchetypeKey(archetype)
  return hexToRgba(STATUS_ARCHETYPE_RAMP[key][600], 0.6)
}

/** Numeric color for Status tab / labels when archetype is known. */
export function statusArchetypeNumeral600(archetype: string | null | undefined): string {
  const key = normalizeStatusArchetypeKey(archetype)
  return STATUS_ARCHETYPE_RAMP[key][600]
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
