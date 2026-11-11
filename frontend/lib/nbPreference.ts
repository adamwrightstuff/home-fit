/**
 * Client-side Natural Beauty preference re-weighting.
 *
 * After a rescore populates nb_topo_raw / nb_landcover_raw / nb_water_raw / nb_topo_base /
 * nb_landcover / nb_water / nb_scenic_cap in the NB breakdown, this module can compute a
 * preference-adjusted NB score without any API call.
 *
 * Formula mirror of natural_beauty.py preference profiles + scoring pipeline.
 */

export type NbPreference = 'mountains' | 'ocean' | 'lakes_rivers' | 'canopy'

// ── Two-part natural beauty preference (current model) ───────────────────────
// Mirrors pillars/natural_beauty.py nb_two_part. Natural beauty is a streets part (green view,
// canopy) and a scenic-setting part (terrain, water), each 0.7 x stronger + 0.3 x weaker, blended
// and rescaled. A preference tilts the blend toward its part. Reads the stored
// details.v9_breakdown component scores. Blend weights and rescale constants are judgment, see
// analysis/natural_beauty_two_part_proposal_2026-10-24.md.
const STREETS_KEYS = ['gvi_score', 'canopy_score'] as const
const SCENERY_KEYS = ['topo_score', 'water_score'] as const
import { NB_SCALE_BLEND, NB_SCALE_SCORE } from '@/lib/nbTwoPartScale'

const PART_LEAD = 0.7
const BLEND_TILT_STREETS = 0.75
const PREFERENCE_V9_PART: Record<NbPreference, 'streets' | 'scenery'> = {
  mountains: 'scenery',
  ocean: 'scenery',
  lakes_rivers: 'scenery',
  canopy: 'streets',
}

export interface V9Breakdown {
  gvi_score?: number
  water_score?: number
  canopy_score?: number
  topo_score?: number
  landcover_score?: number
  bio_score?: number
  inputs?: { water_type?: string; gvi_pct?: number | null; canopy_pct?: number | null }
}

function leadPair(a: number | undefined, b: number | undefined): number | null {
  const vals = [a, b].filter((v): v is number => typeof v === 'number').sort((x, y) => y - x)
  if (vals.length === 0) return null
  if (vals.length === 1) return vals[0]
  return PART_LEAD * vals[0] + (1 - PART_LEAD) * vals[1]
}

/**
 * Re-score natural beauty for one or more scenery preferences. Mirrors nb_two_part() in
 * natural_beauty.py: the preference tilts the blend toward the streets part (tree canopy) or the
 * scenic-setting part (mountains, ocean, lakes and rivers); picks from both sides average out.
 * An ocean or lakes/rivers pick that does not match the place's water type cuts its water score
 * to a quarter.
 */
export function applyNbPreferencesV9(
  v9: V9Breakdown | undefined | null,
  preferences: NbPreference[],
): number | null {
  if (!v9 || preferences.length === 0) return null
  const waterType = v9.inputs?.water_type

  const eff: Record<string, number | undefined> = {}
  for (const key of [...STREETS_KEYS, ...SCENERY_KEYS]) {
    const val = (v9 as Record<string, unknown>)[key]
    if (typeof val === 'number') eff[key] = val
  }
  if (waterType && typeof eff['water_score'] === 'number') {
    for (const pref of preferences) {
      if (pref === 'ocean' || pref === 'lakes_rivers') {
        const isCoastal = /ocean|coast|bay|harbor|sea/i.test(waterType)
        const isLakeRiver = /lake|reservoir|river|stream|canal/i.test(waterType)
        const match = pref === 'ocean' ? isCoastal : isLakeRiver
        if (!match) eff['water_score'] = eff['water_score']! * 0.25
      }
    }
  }

  const shares = preferences
    .map((p) => PREFERENCE_V9_PART[p])
    .filter(Boolean)
    .map((part) => (part === 'streets' ? BLEND_TILT_STREETS : 1 - BLEND_TILT_STREETS))
  if (shares.length === 0) return null
  const w = shares.reduce((a, b) => a + b, 0) / shares.length

  // No greenery measurement (both inputs exactly zero): do not score a made-up zero.
  const inp = v9.inputs
  if (inp && 'gvi_pct' in inp && !inp.gvi_pct && !inp.canopy_pct) {
    eff['gvi_score'] = undefined
    eff['canopy_score'] = undefined
  }
  const streets = leadPair(eff['gvi_score'], eff['canopy_score'])
  const scenery = leadPair(eff['topo_score'], eff['water_score'])
  if (streets === null && scenery === null) return null
  const blend =
    streets === null ? (scenery as number) : scenery === null ? streets : w * streets + (1 - w) * scenery
  return Math.round(blendToScore(blend) * 100) / 100
}

/** Piecewise-linear lookup of the blend in the quantile table (calibration to the old score, not evidence). */
function blendToScore(blend: number): number {
  const xs = NB_SCALE_BLEND
  const ys = NB_SCALE_SCORE
  if (blend <= xs[0]) return ys[0]
  if (blend >= xs[xs.length - 1]) return ys[ys.length - 1]
  let lo = 0
  let hi = xs.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (xs[mid] <= blend) lo = mid
    else hi = mid
  }
  return ys[lo] + ((ys[hi] - ys[lo]) * (blend - xs[lo])) / (xs[hi] - xs[lo])
}
