import type { ScoreResponse } from '@/types/api'
import { DEFAULT_PRIORITIES, type PillarPriorities } from '@/components/SearchOptions'
/** Explorer filters that rewrite pillar scores (as opposed to filters that only hide places). */
export type SchoolLevel = 'elementary' | 'middle' | 'high'
export const ALL_SCHOOL_LEVELS: SchoolLevel[] = ['elementary', 'middle', 'high']

export interface ScoreAffectingFilters {
  filterSchoolType: 'any' | 'public_only' | 'charter' | 'both'
  /** Grades to score (default all three = the stored score). Applies to the public-schools view only. */
  filterSchoolLevels?: SchoolLevel[]
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

  // School type: Public (the default) is the score as stored; Charter scores the nearby charters; both averages the two
  // when at least 3 charters are rated nearby (otherwise Public, with a note). Charters admit by lottery, so "both" is an
  // optimistic view and is labelled as such.
  if (f.filterSchoolType === 'public_only' || f.filterSchoolType === 'charter' || f.filterSchoolType === 'both') {
    const edu = (out.livability_pillars as any)?.quality_education
    const split = edu?.breakdown?.split
    if (split) {
      const pub = split.public, ch = split.charter
      const noData = () => withPillar(out, 'quality_education', { ...edu, score: null, status: 'no_data' })
      if (f.filterSchoolType === 'charter') {
        out = ch?.score == null ? noData() : withPillar(out, 'quality_education', {
          ...edu, score: ch.score,
          breakdown: { ...edu.breakdown, split_view: 'charter', split_n_rated: ch.n_rated, split_confidence: ch.confidence,
            split_note: `Nearby charter schools only (${ch.n_rated} rated${ch.confidence === 'thin' ? ', thin' : ''}); charters admit by lottery.` },
        })
      } else if (f.filterSchoolType === 'both') {
        if (ch?.score != null && ch.confidence === 'ok' && pub?.score != null) {
          out = withPillar(out, 'quality_education', {
            ...edu, score: Math.min(100, (pub.score + ch.score) / 2),
            breakdown: { ...edu.breakdown, split_view: 'both', split_n_rated: ch.n_rated, split_confidence: ch.confidence,
              split_note: `Average of assigned public schools and ${ch.n_rated} nearby charters; includes charter options that admit by lottery.` },
          })
        } else {
          out = withPillar(out, 'quality_education', {
            ...edu,
            breakdown: { ...edu.breakdown, split_view: 'both_fallback',
              split_note: 'Fewer than 3 rated charters nearby, so this shows public schools only.' },
          })
        }
      }
      // 'public_only' (older saved filters) is the stored score: nothing to change
    } else if (f.filterSchoolType !== 'public_only' && edu?.by_level) {
      // Fallback for payloads without a split: top-3-per-level approximation.
      const wantCharter = f.filterSchoolType === 'charter'
      const allSchools: { rating: number; is_charter_school?: boolean | null }[] = Object.values(edu.by_level).flat() as any
      const filtered = allSchools.filter((s) => (wantCharter ? s.is_charter_school === true : s.is_charter_school === false))
      if (filtered.length === 0) {
        out = withPillar(out, 'quality_education', { ...edu, score: null, status: 'no_data' })
      } else {
        const baseAvg = filtered.reduce((sum, s) => sum + (s.rating ?? 0), 0) / filtered.length
        const breakdown = edu.breakdown ?? {}
        out = withPillar(out, 'quality_education', { ...edu, score: Math.min(100, baseAvg + (breakdown.access_bonus ?? 0) + (breakdown.early_ed_bonus ?? 0)), breakdown: { ...breakdown, base_avg_rating: baseAvg } })
      }
    }
  }

  // Grades: with fewer than all three levels picked, rescore from the stored per-level scores (public view only; the
  // charter split has no per-level scores). Picking all three leaves the stored score alone, which already leaves out
  // a citywide-choice level that is the same for every neighborhood; picking that level on its own shows it. The
  // early-education bonus is a preschool measure, so it counts only when elementary is picked.
  const levelsPicked = (f.filterSchoolLevels ?? ALL_SCHOOL_LEVELS).filter((l) => ALL_SCHOOL_LEVELS.includes(l))
  if (levelsPicked.length > 0 && levelsPicked.length < ALL_SCHOOL_LEVELS.length &&
      (f.filterSchoolType === 'any' || f.filterSchoolType === 'public_only')) {
    const edu = (out.livability_pillars as any)?.quality_education
    const levels = edu?.breakdown?.levels
    if (levels) {
      const picked = levelsPicked.filter((l) => typeof levels[l]?.score === 'number')
      if (picked.length === 0) {
        out = withPillar(out, 'quality_education', { ...edu, score: null, status: 'no_data' })
      } else {
        const avg = picked.reduce((sum, l) => sum + levels[l].score, 0) / picked.length
        const bonus = levelsPicked.includes('elementary') ? (edu.breakdown.early_ed_bonus ?? 0) : 0
        const label = levelsPicked.join(' + ')
        out = withPillar(out, 'quality_education', {
          ...edu, score: Math.min(100, avg + bonus),
          breakdown: { ...edu.breakdown, base_avg_rating: avg, levels_view: levelsPicked,
            split_note: `Scored on ${label} only${picked.length < levelsPicked.length ? ' (a level with no rated school is left out)' : ''}.` },
          summary: { ...(edu.summary ?? {}), base_avg_rating: Math.round(avg * 100) / 100 },
        })
      }
    }
  }

  // NB scenery and AO sub-component preferences aren't handled here -- they're applied
  // separately in the catalog page's adjustedPlaces pipeline via
  // applyScenerySubPreferencesToScore (lib/reweight.ts), which patches
  // natural_beauty.score/active_outdoors.score directly (and, via total_score being
  // recomputed downstream, the overall HomeFit score too).

  return out
}

/** Snapshot of the Explorer's current weights + filters, handed to Compare. */
export interface CompareContext {
  priorities: PillarPriorities
  filters: ScoreAffectingFilters & {
    filterNbTypes: string[]
    filterAoTypes: string[]
  }
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
    const opts = JSON.parse(localStorage.getItem('homefit_search_options') ?? 'null')
    const pri = opts?.priorities
    if (!pri || typeof pri !== 'object') return null
    const f = opts.filters ?? {}
    return {
      priorities: { ...DEFAULT_PRIORITIES, ...pri } as PillarPriorities,
      filters: {
        filterSchoolType: f.filterSchoolType === 'public_only' || f.filterSchoolType === 'charter' ? f.filterSchoolType : 'any',
        filterSchoolLevels: Array.isArray(f.filterSchoolLevels)
          ? f.filterSchoolLevels.filter((l: string) => (ALL_SCHOOL_LEVELS as string[]).includes(l))
          : ALL_SCHOOL_LEVELS,
        filterNbTypes: Array.isArray(f.filterNbTypes) ? f.filterNbTypes : [],
        filterAoTypes: Array.isArray(f.filterAoTypes) ? f.filterAoTypes : [],
      },
    }
  } catch {
    return null
  }
}
