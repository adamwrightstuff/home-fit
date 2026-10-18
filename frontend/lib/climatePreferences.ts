import type { ClimateIndicators } from './catalogMapTypes'

/** Hard filters, kept apart from the preferences below: they only remove places. */
export interface ClimateMustHaves {
  no_cold_winters?: boolean
  no_hot_summers?: boolean
  no_grey_days?: boolean
  no_big_swings?: boolean
}

export interface ClimatePreferences {
  must_haves?: ClimateMustHaves
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

function greyIndex(avg_solar: number, annual_precip_in: number): number {
  const solarNorm = clamp((avg_solar - 3.4) / (5.8 - 3.4), 0, 1)
  const precipNorm = clamp((annual_precip_in - 6) / (55 - 6), 0, 1)
  return 0.6 * (1 - solarNorm) + 0.4 * precipNorm
}

/** "Cold winters" must-have: Köppen's cold-winter test (US convention), coldest month's mean below 32°F (0°C). */
export const COLD_MUST_HAVE_COLDEST_MONTH_F = 32
/** "Hot summers" must-have: Köppen's hot-summer test, July mean above 71.6°F (22°C). */
export const HEAT_MUST_HAVE_JULY_F = 71.6
/** "Grey, rainy" must-have: grey-day index (sunshine and rainfall blend) above this. */
export const GREY_MUST_HAVE_INDEX = 0.85
/** "Big seasonal swings" must-have: July minus January mean above this many °F. */
export const SWING_MUST_HAVE_F = 40

/** Which of the user's climate must-haves this place fails; empty when none or no climate data. */
export function climateMustHaveFails(
  climate: ClimateIndicators | undefined,
  mh: ClimateMustHaves | undefined,
): (keyof ClimateMustHaves)[] {
  if (!climate || !mh) return []
  const out: (keyof ClimateMustHaves)[] = []
  if (mh.no_cold_winters && typeof climate.coldest_month_f === 'number' && climate.coldest_month_f < COLD_MUST_HAVE_COLDEST_MONTH_F) out.push('no_cold_winters')
  if (mh.no_hot_summers && typeof climate.jul_f === 'number' && climate.jul_f > HEAT_MUST_HAVE_JULY_F) out.push('no_hot_summers')
  if (mh.no_grey_days && typeof climate.avg_solar === 'number' && typeof climate.annual_precip_in === 'number' && greyIndex(climate.avg_solar, climate.annual_precip_in) > GREY_MUST_HAVE_INDEX) out.push('no_grey_days')
  if (mh.no_big_swings && typeof climate.swing_f === 'number' && climate.swing_f > SWING_MUST_HAVE_F) out.push('no_big_swings')
  return out
}

export function hasClimateMustHaves(mh: ClimateMustHaves | undefined): boolean {
  return !!mh && Object.values(mh).some(Boolean)
}

/**
 * Keeps only the must-haves from saved or quiz state. Older "dealbreaker" and "want_consistency"
 * picks convert to must-haves; the retired love/vibe/tolerance preferences are dropped.
 */
export function normalizeClimatePrefs(raw: unknown): ClimatePreferences {
  const r = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const must: ClimateMustHaves = { ...((r.must_haves as ClimateMustHaves | undefined) ?? {}) }
  if (r.cold_tolerance === 'dealbreaker') must.no_cold_winters = true
  if (r.heat_tolerance === 'dealbreaker') must.no_hot_summers = true
  if (r.rain_tolerance === 'dealbreaker') must.no_grey_days = true
  if (r.seasons === 'want_consistency') must.no_big_swings = true
  return hasClimateMustHaves(must) ? { must_haves: must } : {}
}
