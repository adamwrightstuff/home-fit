'use client'

import { PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import type { PillarPriorities } from '@/components/SearchOptions'
import { pillarDiffs, type TwinMatchResult } from '@/lib/twinSimilarity'
import { inferCatalogMetro } from '@/lib/catalogMapTypes'
import ArchetypeBadge from '@/components/catalog/ArchetypeBadge'
import MetroDot from '@/components/catalog/MetroDot'
import SignalStrengthDots from '@/components/catalog/SignalStrengthDots'
import type { CatalogMapPlaceWithMetro } from '@/lib/catalogMapTypes'
import TwinDiffRows from '@/components/catalog/TwinDiffRows'

interface TwinResultCardProps {
  query: CatalogMapPlace
  result: TwinMatchResult
  priorities: PillarPriorities
  selectedPillars: PillarKey[]
  selected?: boolean
  /** When false, hide pillar diff rows (e.g. full detail shown elsewhere). */
  showPillarDiffs?: boolean
  onSelect?: () => void
}

export default function TwinResultCard({
  query,
  result,
  priorities,
  selectedPillars,
  selected,
  showPillarDiffs = true,
  onSelect,
}: TwinResultCardProps) {
  const place = result.place as CatalogMapPlaceWithMetro
  const metro = inferCatalogMetro(place)
  const rw = reweightScoreResponseFromPriorities(place.score, priorities)
  const hf = typeof rw.total_score === 'number' && Number.isFinite(rw.total_score) ? rw.total_score : null
  const br = place.score.status_signal_breakdown
  const archetype = br?.archetype ?? null

  const matchingSet = new Set(selectedPillars)
  const matchingDiffs = pillarDiffs(query, place, selectedPillars).sort(
    (a, b) => Math.abs(b.diff) - Math.abs(a.diff)
  )
  const excludedPillars = PILLAR_ORDER.filter((k) => !matchingSet.has(k))
  const excludedDiffs = excludedPillars.length ? pillarDiffs(query, place, excludedPillars) : []

  const typeLabel = (place.catalog.type || '').trim()
  const typePretty = typeLabel ? typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1).toLowerCase() : ''

  return (
    <div
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onClick={onSelect}
      onKeyDown={
        onSelect
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onSelect()
              }
            }
          : undefined
      }
      className={`relative rounded-2xl border bg-[var(--hf-card-bg)] p-3 shadow-[var(--hf-card-shadow-sm)] ${
        selected ? 'border-[var(--hf-primary-1)] ring-2 ring-[var(--hf-primary-1)]/25' : 'border-[var(--hf-border)]'
      } ${onSelect ? 'cursor-pointer transition hover:bg-[var(--hf-hover-bg)]' : ''}`}
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

      {showPillarDiffs && (
        <div className="mt-3 border-t border-[var(--hf-border)] pt-2">
          <div className="mb-1.5 text-[0.6rem] font-bold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
            Used in matching
          </div>
          <TwinDiffRows rows={matchingDiffs} />
          {excludedDiffs.length > 0 && (
            <div className="mt-3 border-t border-dashed border-[var(--hf-border)] pt-2">
              <div className="mb-1.5 text-[0.6rem] font-bold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
                Not used in matching
              </div>
              <TwinDiffRows rows={excludedDiffs} variant="muted" />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
