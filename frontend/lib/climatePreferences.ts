import type { ClimateIndicators } from './catalogMapTypes'

export type ColdTolerance = 'dealbreaker' | 'tolerable' | 'love'
export type HeatTolerance = 'dealbreaker' | 'fine' | 'love'
export type RainTolerance = 'dealbreaker' | 'meh' | 'vibe'
export type SeasonsPref = 'want_4' | 'mild_ok' | 'want_consistency'

export interface ClimatePreferences {
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
  if (pref === 'dealbreaker') return linear(jan_f, 35, 52)
  return linear(jan_f, 45, 20) // love cold
}

function axisHeat(jul_f: number, pref: HeatTolerance): number {
  if (pref === 'fine') return 50
  if (pref === 'dealbreaker') return linear(jul_f, 80, 65)
  return linear(jul_f, 70, 85) // love heat
}

function axisRain(avg_solar: number, annual_precip_in: number, pref: RainTolerance): number {
  if (pref === 'meh') return 50
  const solarNorm = clamp((avg_solar - 3.4) / (5.8 - 3.4), 0, 1)
  const precipNorm = clamp((annual_precip_in - 6) / (55 - 6), 0, 1)
  const grey = 0.6 * (1 - solarNorm) + 0.4 * precipNorm
  if (pref === 'dealbreaker') return clamp((1 - grey) * 100, 0, 100)
  return clamp(grey * 100, 0, 100) // vibe
}

function axisSeasons(swing_f: number, pref: SeasonsPref): number {
  if (pref === 'mild_ok') return 50
  if (pref === 'want_4') return linear(swing_f, 18, 40)
  return linear(swing_f, 30, 10) // want consistency
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
