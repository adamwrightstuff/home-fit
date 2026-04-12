'use client'

import { PILLAR_META, type PillarKey } from '@/lib/pillars'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import type { PillarPriorities } from '@/components/SearchOptions'
import { topPillarDiffsByMagnitude, type TwinMatchResult } from '@/lib/twinSimilarity'
import { inferCatalogMetro } from '@/lib/catalogMapTypes'
import ArchetypeBadge from '@/components/catalog/ArchetypeBadge'
import MetroDot from '@/components/catalog/MetroDot'
import SignalStrengthDots from '@/components/catalog/SignalStrengthDots'
import type { CatalogMapPlaceWithMetro } from '@/lib/catalogMapTypes'

interface TwinResultCardProps {
  query: CatalogMapPlace
  result: TwinMatchResult
  priorities: PillarPriorities
  selectedPillars: PillarKey[]
}

export default function TwinResultCard({ query, result, priorities, selectedPillars }: TwinResultCardProps) {
  const place = result.place as CatalogMapPlaceWithMetro
  const metro = inferCatalogMetro(place)
  const rw = reweightScoreResponseFromPriorities(place.score, priorities)
  const hf = typeof rw.total_score === 'number' && Number.isFinite(rw.total_score) ? rw.total_score : null
  const br = place.score.status_signal_breakdown
  const archetype = br?.archetype ?? null
  const diffs = topPillarDiffsByMagnitude(query, place, selectedPillars)

  const typeLabel = (place.catalog.type || '').trim()
  const typePretty = typeLabel ? typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1).toLowerCase() : ''

  return (
    <div
      className="relative rounded-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] p-3 shadow-[var(--hf-card-shadow-sm)]"
      style={{ position: 'relative' }}
    >
      <div
        className="absolute right-3 top-3 text-2xl font-bold tabular-nums"
        style={{ color: '#6B5CE7' }}
      >
        {result.matchPct}%
      </div>

      <div className="pr-16">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-[var(--hf-text-primary)]">{place.catalog.name}</h3>
          <MetroDot metro={metro} />
        </div>
        <p className="mt-0.5 text-[0.7rem] text-[var(--hf-text-secondary)]">
          {place.catalog.county_borough}, {place.catalog.state_abbr}
          {typePretty ? ` · ${typePretty}` : ''}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <ArchetypeBadge archetype={archetype} />
          <SignalStrengthDots breakdown={br} statusSignalScore={place.score.status_signal} />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
            HomeFit
          </span>
          <span className="text-lg font-bold tabular-nums" style={{ color: '#6B5CE7' }}>
            {hf != null ? hf.toFixed(1) : '—'}
          </span>
        </div>
      </div>

      <div className="mt-3 space-y-1.5 border-t border-[var(--hf-border)] pt-2">
        {diffs.map((d) => {
          const abs = Math.abs(d.diff)
          const barColor =
            d.diff > 5 ? '#1D9E75' : d.diff < -5 ? '#E76B5C' : 'rgba(100,100,100,0.35)'
          return (
            <div key={d.key} className="flex items-center gap-2 text-[0.7rem]">
              <span className="min-w-0 flex-1 truncate text-[var(--hf-text-primary)]">
                {PILLAR_META[d.key].name}
              </span>
              <span className="w-10 shrink-0 tabular-nums text-right text-[var(--hf-text-secondary)]">
                {d.diff > 0 ? '+' : ''}
                {d.diff.toFixed(0)}
              </span>
              <div className="h-1.5 w-14 shrink-0 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
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
    </div>
  )
}
