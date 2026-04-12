'use client'

import { Search } from 'lucide-react'
import type { CatalogMapPlace, CatalogMapPlaceWithMetro } from '@/lib/catalogMapTypes'
import { catalogRowKey, inferCatalogMetro } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import type { PillarKey } from '@/lib/pillars'
import type { TwinMatchResult } from '@/lib/twinSimilarity'
import TwinResultCard from '@/components/catalog/TwinResultCard'
import MetroDot from '@/components/catalog/MetroDot'

interface TwinFinderPanelProps {
  places: CatalogMapPlaceWithMetro[]
  twinSearchText: string
  twinQueryKey: string | null
  queryPlace: CatalogMapPlace | null
  twinRanked: TwinMatchResult[]
  priorities: PillarPriorities
  selectedPillars: PillarKey[]
  onSelectQuery: (key: string) => void
}

export default function TwinFinderPanel({
  places,
  twinSearchText,
  twinQueryKey,
  queryPlace,
  twinRanked,
  priorities,
  selectedPillars,
  onSelectQuery,
}: TwinFinderPanelProps) {
  const q = twinSearchText.trim().toLowerCase()
  const autocomplete =
    !twinQueryKey && q.length > 0
      ? places.filter((p) => {
          const name = (p.catalog.name || '').toLowerCase()
          const county = (p.catalog.county_borough || '').toLowerCase()
          return name.includes(q) || county.includes(q) || (p.catalog.state_abbr || '').toLowerCase().includes(q)
        }).slice(0, 24)
      : []

  if (!twinQueryKey && twinSearchText.trim() === '') {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 pb-24 text-center">
        <Search className="h-12 w-12 text-[var(--hf-text-tertiary)] opacity-60" strokeWidth={1.25} />
        <p className="max-w-sm text-sm font-medium text-[var(--hf-text-secondary)]">
          Select a neighborhood to find its closest match in another metro
        </p>
      </div>
    )
  }

  if (!twinQueryKey && twinSearchText.trim() !== '') {
    return (
      <div className="min-h-0 flex-1 overflow-auto px-2 pb-28">
        <ul className="space-y-1">
          {autocomplete.map((p) => {
            const key = catalogRowKey(p.catalog)
            const metro = inferCatalogMetro(p)
            const ty = (p.catalog.type || '').trim()
            const typePretty = ty ? ty.charAt(0).toUpperCase() + ty.slice(1).toLowerCase() : ''
            return (
              <li key={key}>
                <button
                  type="button"
                  className="flex w-full items-start gap-2 rounded-xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] px-3 py-2.5 text-left shadow-sm transition hover:bg-[var(--hf-hover-bg)]"
                  onClick={() => onSelectQuery(key)}
                >
                  <MetroDot metro={metro} />
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-[var(--hf-text-primary)]">{p.catalog.name}</div>
                    <div className="text-[0.75rem] text-[var(--hf-text-secondary)]">
                      {p.catalog.county_borough}, {p.catalog.state_abbr}
                      {typePretty ? ` · ${typePretty}` : ''}
                    </div>
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
        {autocomplete.length === 0 && (
          <p className="py-8 text-center text-sm text-[var(--hf-text-secondary)]">No matches.</p>
        )}
      </div>
    )
  }

  if (!queryPlace) return null

  return (
    <div className="min-h-0 flex-1 overflow-auto px-2 pb-28">
      <div className="mx-auto grid max-w-lg gap-3 sm:max-w-none sm:grid-cols-2">
        {twinRanked.map((r) => (
          <TwinResultCard
            key={r.key}
            query={queryPlace}
            result={r}
            priorities={priorities}
            selectedPillars={selectedPillars}
          />
        ))}
      </div>
    </div>
  )
}
