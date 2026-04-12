'use client'

import { useRouter } from 'next/navigation'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import { getAllCatalogIndexDisplay } from '@/lib/catalogMapGeo'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { pillarDiffs } from '@/lib/twinSimilarity'
import RadarChart from '@/components/catalog/RadarChart'
import { writeCatalogResultsHydrate } from '@/lib/catalogResultsHydrate'
import { buildResultsCacheKey, buildResultsUrl } from '@/lib/resultsShare'

interface CatalogTwinDetailSheetProps {
  query: CatalogMapPlace
  twin: CatalogMapPlace
  matchPct: number
  pillars: PillarKey[]
  priorities: PillarPriorities
  snap: 'peek' | 'expanded'
  onSnapChange: (s: 'peek' | 'expanded') => void
  onClose: () => void
}

export default function CatalogTwinDetailSheet({
  query,
  twin,
  matchPct,
  pillars,
  priorities,
  snap,
  onSnapChange,
  onClose,
}: CatalogTwinDetailSheetProps) {
  const router = useRouter()
  const expanded_vh = 70
  const qIdx = getAllCatalogIndexDisplay(query, priorities)
  const rwTwin = reweightScoreResponseFromPriorities(twin.score, priorities)

  const queryScores = {} as Record<PillarKey, number>
  const twinScores = {} as Record<PillarKey, number>
  const qp = query.score.livability_pillars as unknown as Record<string, { score?: number }>
  const tp = twin.score.livability_pillars as unknown as Record<string, { score?: number }>
  for (const k of pillars) {
    queryScores[k] = typeof qp[k]?.score === 'number' ? qp[k]!.score! : 0
    twinScores[k] = typeof tp[k]?.score === 'number' ? tp[k]!.score! : 0
  }

  const diffs = pillarDiffs(query, twin, pillars)

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
    <div
      className="fixed left-0 right-0 z-20 flex flex-col rounded-t-2xl shadow-[var(--hf-card-shadow)]"
      style={{
        bottom: 0,
        maxHeight: snap === 'expanded' ? `${expanded_vh}vh` : undefined,
        transition: 'max-height 0.28s ease',
        padding: `0 16px max(12px, env(safe-area-inset-bottom)) 16px`,
        background: 'var(--hf-card-bg)',
        borderTop: '1px solid var(--hf-border)',
      }}
    >
      <button
        type="button"
        className="flex w-full shrink-0 flex-col"
        onClick={() => onSnapChange(snap === 'peek' ? 'expanded' : 'peek')}
        aria-expanded={snap === 'expanded'}
      >
        <div
          style={{
            width: 36,
            height: 4,
            borderRadius: 2,
            background: 'var(--color-border-primary)',
            margin: '8px auto 10px',
          }}
        />
      </button>

      <div className="min-h-0 flex-1 overflow-y-auto pb-2">
        <div className="mb-2 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xl font-bold tabular-nums" style={{ color: '#6B5CE7' }}>
              {matchPct}%
            </div>
            <div className="text-base font-semibold text-[var(--hf-text-primary)]">{twin.catalog.name}</div>
            <div className="text-xs text-[var(--hf-text-secondary)]">
              {twin.catalog.county_borough}, {twin.catalog.state_abbr} · {twin.catalog.type}
            </div>
          </div>
          <button
            type="button"
            className="shrink-0 rounded-lg border border-[var(--hf-border)] bg-[var(--hf-hover-bg)] px-2 py-1 text-xs font-bold"
            onClick={onClose}
          >
            Clear
          </button>
        </div>

        <div className="mb-2 text-xs text-[var(--hf-text-secondary)]">
          HomeFit {typeof rwTwin.total_score === 'number' ? rwTwin.total_score.toFixed(1) : '—'} · vs query HomeFit{' '}
          {qIdx.homefit != null ? qIdx.homefit.toFixed(1) : '—'}
        </div>

        <RadarChart pillars={pillars} queryScores={queryScores} twinScores={twinScores} size={200} />

        <div className="mt-3 space-y-1.5">
          <div className="text-[0.65rem] font-bold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
            Pillar differences (twin − query)
          </div>
          {diffs.map((d) => {
            const abs = Math.abs(d.diff)
            const barColor =
              d.diff > 5 ? '#1D9E75' : d.diff < -5 ? '#E76B5C' : 'rgba(100,100,100,0.35)'
            return (
              <div key={d.key} className="flex items-center gap-2 text-[0.75rem]">
                <span className="min-w-0 flex-1 truncate text-[var(--hf-text-primary)]">
                  {PILLAR_META[d.key].name}
                </span>
                <span className="w-10 shrink-0 tabular-nums text-right text-[var(--hf-text-secondary)]">
                  {d.diff > 0 ? '+' : ''}
                  {d.diff.toFixed(0)}
                </span>
                <div className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min(100, abs)}%`,
                      background: barColor,
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>

        <button
          type="button"
          className="mt-4 w-full rounded-xl py-2.5 text-center text-sm font-bold"
          style={{
            background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))',
            color: '#fff',
          }}
          onClick={handleFullBreakdown}
        >
          Full breakdown
        </button>
      </div>
    </div>
  )
}
