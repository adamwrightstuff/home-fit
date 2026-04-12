'use client'

import { useRouter } from 'next/navigation'
import { PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import { getAllCatalogIndexDisplay } from '@/lib/catalogMapGeo'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { pillarDiffs } from '@/lib/twinSimilarity'
import RadarChart from '@/components/catalog/RadarChart'
import TwinDiffRows from '@/components/catalog/TwinDiffRows'
import { writeCatalogResultsHydrate } from '@/lib/catalogResultsHydrate'
import { buildResultsCacheKey, buildResultsUrl } from '@/lib/resultsShare'
interface TwinCandidateDetailContentProps {
  query: CatalogMapPlace
  twin: CatalogMapPlace
  matchPct: number
  /** Pillars used in twin matching. */
  matchingPillars: PillarKey[]
  priorities: PillarPriorities
}

export default function TwinCandidateDetailContent({
  query,
  twin,
  matchPct,
  matchingPillars,
  priorities,
}: TwinCandidateDetailContentProps) {
  const router = useRouter()
  const qIdx = getAllCatalogIndexDisplay(query, priorities)
  const rwTwin = reweightScoreResponseFromPriorities(twin.score, priorities)

  const queryScores = {} as Record<PillarKey, number>
  const twinScores = {} as Record<PillarKey, number>
  const qp = query.score.livability_pillars as unknown as Record<string, { score?: number }>
  const tp = twin.score.livability_pillars as unknown as Record<string, { score?: number }>
  for (const k of matchingPillars) {
    queryScores[k] = typeof qp[k]?.score === 'number' ? qp[k]!.score! : 0
    twinScores[k] = typeof tp[k]?.score === 'number' ? tp[k]!.score! : 0
  }

  const matchingSet = new Set(matchingPillars)
  const matchingDiffs = pillarDiffs(query, twin, matchingPillars).sort(
    (a, b) => Math.abs(b.diff) - Math.abs(a.diff)
  )
  const excludedPillars = PILLAR_ORDER.filter((k) => !matchingSet.has(k))
  const excludedDiffs = excludedPillars.length
    ? pillarDiffs(query, twin, excludedPillars).sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff))
    : []

  const handleFullBreakdown = () => {
    const prioritiesJson = JSON.stringify(priorities)
    const routeParams = {
      location: twin.catalog.search_query,
      prioritiesJson,
      job_categories: null as string | null,
      include_chains: false,
      enable_schools: false,
      natural_beauty_preference: null as string | null,
      built_character_preference: null as string | null,
      built_density_preference: null as string | null,
    }
    const cacheKey = buildResultsCacheKey(routeParams)
    writeCatalogResultsHydrate({ v: 1, cacheKey, score: twin.score })
    router.push(buildResultsUrl(routeParams))
  }

  return (
    <div className="rounded-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] p-4 shadow-[var(--hf-card-shadow-sm)]">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-2xl font-bold tabular-nums" style={{ color: '#6B5CE7' }}>
            {matchPct}% match
          </div>
          <div className="text-base font-semibold text-[var(--hf-text-primary)]">{twin.catalog.name}</div>
          <div className="text-xs text-[var(--hf-text-secondary)]">
            {twin.catalog.county_borough}, {twin.catalog.state_abbr} · {twin.catalog.type}
          </div>
        </div>
      </div>

      <div className="mb-2 text-xs text-[var(--hf-text-secondary)]">
        Twin HomeFit {typeof rwTwin.total_score === 'number' ? rwTwin.total_score.toFixed(1) : '—'} · Query HomeFit{' '}
        {qIdx.homefit != null ? qIdx.homefit.toFixed(1) : '—'}
      </div>

      <div className="flex justify-center py-2">
        <RadarChart pillars={matchingPillars} queryScores={queryScores} twinScores={twinScores} size={300} />
      </div>

      <div className="mt-3">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
          Pillar differences (twin − query) — used in matching
        </div>
        <TwinDiffRows rows={matchingDiffs} />
      </div>

      {excludedDiffs.length > 0 && (
        <div className="mt-4 border-t border-dashed border-[var(--hf-border)] pt-3">
          <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
            Not used in matching
          </div>
          <TwinDiffRows rows={excludedDiffs} variant="muted" />
        </div>
      )}

      <button
        type="button"
        className="mt-4 w-full rounded-xl py-2.5 text-center text-sm font-bold text-white"
        style={{
          background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))',
        }}
        onClick={handleFullBreakdown}
      >
        Full breakdown
      </button>
    </div>
  )
}
