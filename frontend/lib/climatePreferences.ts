import type { ClimateIndicators } from './catalogMapTypes'

export type ColdTolerance = 'tolerable' | 'love'
export type HeatTolerance = 'fine' | 'love'
export type RainTolerance = 'meh' | 'vibe'
export type SeasonsPref = 'want_4' | 'mild_ok' | 'want_consistency'

/** Hard filters, kept apart from the preferences below: they only remove places. */
export interface ClimateMustHaves {
  no_cold_winters?: boolean
  no_hot_summers?: boolean
  no_grey_days?: boolean
  no_big_swings?: boolean
}

export interface ClimatePreferences {
  must_haves?: ClimateMustHaves
  cold_tolerance?: ColdTolerance
  heat_tolerance?: HeatTolerance
  rain_tolerance?: RainTolerance
  seasons?: SeasonsPref
}

export interface ClimateMatchResult {
  score: number
  axes: {
    cold_winter?: number
    summer_heat?: number
    rain_grey?: number
    seasonal?: number
  }
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

function linear(val: number, bad: number, good: number): number {
  if (good === bad) return 50
  return clamp(((val - bad) / (good - bad)) * 100, 0, 100)
}

function axisCold(jan_f: number, pref: ColdTolerance): number {
  if (pref === 'tolerable') return 50
  return linear(jan_f, 45, 20) // love cold
}

function axisHeat(jul_f: number, pref: HeatTolerance): number {
  if (pref === 'fine') return 50
  return linear(jul_f, 70, 85) // love heat
}

function greyIndex(avg_solar: number, annual_precip_in: number): number {
  const solarNorm = clamp((avg_solar - 3.4) / (5.8 - 3.4), 0, 1)
  const precipNorm = clamp((annual_precip_in - 6) / (55 - 6), 0, 1)
  return 0.6 * (1 - solarNorm) + 0.4 * precipNorm
}

function axisRain(avg_solar: number, annual_precip_in: number, pref: RainTolerance): number {
  if (pref === 'meh') return 50
  return clamp(greyIndex(avg_solar, annual_precip_in) * 100, 0, 100) // vibe
}

function axisSeasons(swing_f: number, pref: SeasonsPref): number {
  if (pref === 'mild_ok') return 50
  if (pref === 'want_4') return linear(swing_f, 18, 40)
  return linear(swing_f, 30, 10) // want consistency
}

/** "Cold winters" must-have: two or more months with a mean temperature below freezing. */
export const COLD_MUST_HAVE_FREEZING_MONTHS = 2
/** "Hot summers" must-have: July mean temperature at or above this many °F. */
export const HEAT_MUST_HAVE_JULY_F = 78
/** "Grey, rainy" must-have: grey-day index (sunshine and rainfall blend) above this. */
export const GREY_MUST_HAVE_INDEX = 0.85
/** "Big seasonal swings" must-have: July minus January mean above this many °F. */
export const SWING_MUST_HAVE_F = 45

/** Which of the user's climate must-haves this place fails; empty when none or no climate data. */
export function climateMustHaveFails(
  climate: ClimateIndicators | undefined,
  mh: ClimateMustHaves | undefined,
): (keyof ClimateMustHaves)[] {
  if (!climate || !mh) return []
  const out: (keyof ClimateMustHaves)[] = []
  if (mh.no_cold_winters && typeof climate.months_below_freezing === 'number' && climate.months_below_freezing >= COLD_MUST_HAVE_FREEZING_MONTHS) out.push('no_cold_winters')
  if (mh.no_hot_summers && typeof climate.jul_f === 'number' && climate.jul_f >= HEAT_MUST_HAVE_JULY_F) out.push('no_hot_summers')
  if (mh.no_grey_days && typeof climate.avg_solar === 'number' && typeof climate.annual_precip_in === 'number' && greyIndex(climate.avg_solar, climate.annual_precip_in) > GREY_MUST_HAVE_INDEX) out.push('no_grey_days')
  if (mh.no_big_swings && typeof climate.swing_f === 'number' && climate.swing_f > SWING_MUST_HAVE_F) out.push('no_big_swings')
  return out
}

export function hasClimateMustHaves(mh: ClimateMustHaves | undefined): boolean {
  return !!mh && Object.values(mh).some(Boolean)
}

/**
 * Splits older saved/quiz preferences, where "dealbreaker" and "want_consistency" doubled as
 * filters, into separate must-haves. Safe to run repeatedly.
 */
export function normalizeClimatePrefs(raw: unknown): ClimatePreferences {
  const r = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const must: ClimateMustHaves = { ...((r.must_haves as ClimateMustHaves | undefined) ?? {}) }
  const out: ClimatePreferences = {}
  if (r.cold_tolerance === 'dealbreaker') must.no_cold_winters = true
  else if (r.cold_tolerance) out.cold_tolerance = r.cold_tolerance as ColdTolerance
  if (r.heat_tolerance === 'dealbreaker') must.no_hot_summers = true
  else if (r.heat_tolerance) out.heat_tolerance = r.heat_tolerance as HeatTolerance
  if (r.rain_tolerance === 'dealbreaker') must.no_grey_days = true
  else if (r.rain_tolerance) out.rain_tolerance = r.rain_tolerance as RainTolerance
  if (r.seasons) out.seasons = r.seasons as SeasonsPref
  if (r.seasons === 'want_consistency') must.no_big_swings = true
  if (hasClimateMustHaves(must)) out.must_haves = must
  return out
}

export function scoreClimateMatch(
  climate: ClimateIndicators | undefined,
  prefs: ClimatePreferences,
): ClimateMatchResult | null {
  if (!climate) return null

  const axes: ClimateMatchResult['axes'] = {}

  if (prefs.cold_tolerance)
    axes.cold_winter = Math.round(axisCold(climate.jan_f, prefs.cold_tolerance) * 10) / 10
  if (prefs.heat_tolerance)
    axes.summer_heat = Math.round(axisHeat(climate.jul_f, prefs.heat_tolerance) * 10) / 10
  if (prefs.rain_tolerance)
    axes.rain_grey = Math.round(axisRain(climate.avg_solar, climate.annual_precip_in, prefs.rain_tolerance) * 10) / 10
  if (prefs.seasons)
    axes.seasonal = Math.round(axisSeasons(climate.swing_f, prefs.seasons) * 10) / 10

  const vals = Object.values(axes).filter((v): v is number => v !== undefined)
  if (!vals.length) return null

  return {
    score: Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10,
    axes,
  }
}

export function hasClimatePreferences(prefs: ClimatePreferences): boolean {
  return !!(prefs.cold_tolerance || prefs.heat_tolerance || prefs.rain_tolerance || prefs.seasons)
}
