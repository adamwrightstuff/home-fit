import type { ScoreResponse } from '@/types/api'
import { DEFAULT_PRIORITIES, type PillarPriorities } from '@/components/SearchOptions'
import { applyNbPreferencesV9, type NbPreference, type V9Breakdown } from '@/lib/nbPreference'
import { applyAoPreferences, applyWaterfrontPreference, type AoPreference, type AoBreakdown, type WaterfrontSubPreference } from '@/lib/aoPreference'

/** Explorer filters that rewrite pillar scores (as opposed to filters that only hide places). */
export interface ScoreAffectingFilters {
  filterSchoolType: 'any' | 'public_only' | 'charter'
  filterNbTypes: string[]
  filterAoTypes: string[]
  filterWaterfrontSubPref: WaterfrontSubPreference | null
}

function withPillar(score: ScoreResponse, key: string, pillar: unknown): ScoreResponse {
  return {
    ...score,
    livability_pillars: { ...score.livability_pillars, [key]: pillar },
  } as ScoreResponse
}

/** Apply the Explorer's score-affecting filters (school type, scenery, outdoors) to one score payload. */
export function applyExplorerScoreAdjustments(score: ScoreResponse, f: ScoreAffectingFilters): ScoreResponse {
  let out = score

  // Recompute quality_education score based on school type preference.
  if (f.filterSchoolType !== 'any') {
    const edu = (out.livability_pillars as any)?.quality_education
    if (edu?.by_level) {
      const allSchools: { rating: number; is_charter_school?: boolean | null }[] = Object.values(edu.by_level).flat() as any
      const filtered = allSchools.filter((s) =>
        f.filterSchoolType === 'public_only' ? s.is_charter_school === false : s.is_charter_school === true
      )
      if (filtered.length === 0) {
        out = withPillar(out, 'quality_education', { ...edu, score: null, status: 'no_data' })
      } else {
        const baseAvg = filtered.reduce((sum, s) => sum + (s.rating ?? 0), 0) / filtered.length
        const breakdown = edu.breakdown ?? {}
        const newScore = Math.min(100, baseAvg + (breakdown.access_bonus ?? 0) + (breakdown.early_ed_bonus ?? 0))
        out = withPillar(out, 'quality_education', { ...edu, score: newScore, breakdown: { ...breakdown, base_avg_rating: baseAvg } })
      }
    }
  }

  // Apply scenery preferences to natural_beauty via v9 preference weighting.
  if (f.filterNbTypes.length > 0 && f.filterNbTypes.length < 4) {
    const nb = (out.livability_pillars as any)?.natural_beauty
    if (nb) {
      const v9 = nb.v9_breakdown as V9Breakdown | undefined
      const prefScore = v9 ? (applyNbPreferencesV9(v9, f.filterNbTypes as NbPreference[]) ?? nb.score) : nb.score
      out = withPillar(out, 'natural_beauty', { ...nb, score: prefScore })
    }
  }

  // Reweight AO score toward selected sub-components (1–2 selected = partial preference;
  // 0 or 3 = no reweighting). When a waterfront sub-preference is also active, first
  // re-weight waterfront_lifestyle toward the chosen water type, then apply AO OWA.
  if (f.filterAoTypes.length > 0 && f.filterAoTypes.length < 3) {
    const ao = (out.livability_pillars as any)?.active_outdoors
    if (ao) {
      const bk = ao.breakdown as AoBreakdown | undefined
      let effectiveBk = bk
      if (f.filterWaterfrontSubPref && f.filterAoTypes.includes('waterfront') && bk) {
        const prefWf = applyWaterfrontPreference(bk, f.filterWaterfrontSubPref)
        if (prefWf !== null) {
          // applyAoPreferences normalizes waterfront_lifestyle (0–25 raw) to 0–100,
          // so convert prefWf (already 0–100) back to raw range before injection.
          effectiveBk = { ...bk, waterfront_lifestyle: (prefWf * 25) / 100 }
        }
      }
      const reweighted = applyAoPreferences(effectiveBk, f.filterAoTypes as AoPreference[])
      if (reweighted !== null) out = withPillar(out, 'active_outdoors', { ...ao, score: reweighted })
    }
  }

  return out
}

/** Snapshot of the Explorer's current weights + score-affecting filters, handed to Compare. */
export interface CompareContext {
  priorities: PillarPriorities
  filters: ScoreAffectingFilters
  /** Explorer's live income (signed-in users load it from their profile, not sessionStorage). */
  householdIncome?: number | null
  /** "Current home" monthly-cost override, applied only to the place with this catalog name. */
  currentHome?: { name: string; monthlyCost: number | null } | null
}

const COMPARE_CONTEXT_KEY = 'homefit_compare_context'

export function writeCompareContext(ctx: CompareContext): void {
  try {
    sessionStorage.setItem(COMPARE_CONTEXT_KEY, JSON.stringify(ctx))
  } catch { /* ignore */ }
}

export function readCompareContext(): CompareContext | null {
  try {
    const raw = sessionStorage.getItem(COMPARE_CONTEXT_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.priorities && parsed?.filters) return parsed as CompareContext
    }
    // Fallback: saved search options (quiz / search page) when Explore hasn't been opened this session.
    const opts = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? 'null')
    const pri = opts?.priorities
    if (!pri || typeof pri !== 'object') return null
    const f = opts.filters ?? {}
    return {
      priorities: { ...DEFAULT_PRIORITIES, ...pri } as PillarPriorities,
      filters: {
        filterSchoolType: f.filterSchoolType === 'public_only' || f.filterSchoolType === 'charter' ? f.filterSchoolType : 'any',
        filterNbTypes: Array.isArray(f.filterNbTypes) ? f.filterNbTypes : [],
        filterAoTypes: Array.isArray(f.filterAoTypes) ? f.filterAoTypes : [],
        filterWaterfrontSubPref: typeof f.filterWaterfrontSubPref === 'string' ? f.filterWaterfrontSubPref : null,
      },
    }
  } catch {
    return null
  }
}
