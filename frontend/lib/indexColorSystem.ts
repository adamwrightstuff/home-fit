/**
 * HomeFit index → color ramp bindings (fixed).
 * HomeFit = purple, Longevity = teal, Happiness = blue, Status Signal = coral.
 */

import type { CatalogMapIndexMode } from '@/lib/catalogMapTypes'

export type IndexRampKey = 'purple' | 'teal' | 'blue' | 'coral'

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
