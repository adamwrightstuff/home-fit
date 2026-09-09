'use client'

import { Search } from 'lucide-react'
import type { CatalogMapPlace, CatalogMapPlaceWithMetro } from '@/lib/catalogMapTypes'
import { catalogRowKey, inferCatalogMetro } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import type { PillarKey } from '@/lib/pillars'
import type { TwinMatchResult } from '@/lib/twinSimilarity'
import TwinResultCard from '@/components/catalog/TwinResultCard'
import TwinCandidateDetailContent from '@/components/catalog/TwinCandidateDetailContent'
import MetroDot from '@/components/catalog/MetroDot'
import { SCENE_ARCHETYPES, type SceneArchetype } from '@/lib/vibeFeatures'

interface TwinFinderPanelProps {
  places: CatalogMapPlaceWithMetro[]
  twinSearchText: string
  twinQueryKey: string | null
  queryPlace: CatalogMapPlace | null
  twinRanked: TwinMatchResult[]
  priorities: PillarPriorities
  selectedPillars: PillarKey[]
  sceneArchetypes: SceneArchetype[]
  onSceneArchetypesChange: (archetypes: SceneArchetype[]) => void
  selectedTwinKey: string | null
  onSelectTwinResult: (key: string | null) => void
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
  sceneArchetypes,
  onSceneArchetypesChange,
  selectedTwinKey,
  onSelectTwinResult,
  onSelectQuery,
}: TwinFinderPanelProps) {
  function toggleArchetype(key: SceneArchetype) {
    onSceneArchetypesChange(
      sceneArchetypes.includes(key)
        ? sceneArchetypes.filter((k) => k !== key)
        : [...sceneArchetypes, key]
    )
  }
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
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6 pb-24 text-center">
        <Search className="h-12 w-12 text-[var(--hf-text-tertiary)] opacity-60" strokeWidth={1.25} />
        <div className="max-w-xs space-y-1.5">
          <p className="text-sm font-semibold text-[var(--hf-text-primary)]">Find your neighborhood&apos;s twin</p>
          <p className="text-xs text-[var(--hf-text-secondary)]">
            Pick any neighborhood and HomeFit compares it across 13 pillars to surface its closest match in a different metro — same character, different city.
          </p>
        </div>
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

  const selectedMatch = selectedTwinKey ? twinRanked.find((r) => r.key === selectedTwinKey) : null

  return (
    <div className="min-h-0 flex-1 overflow-auto px-2 pb-28">
      {selectedMatch && (
        <div className="mx-auto mb-4 max-w-lg sm:max-w-2xl">
          <TwinCandidateDetailContent
            query={queryPlace}
            twin={selectedMatch.place}
            matchPct={selectedMatch.matchPct}
            matchingPillars={selectedPillars}
            priorities={priorities}
          />
        </div>
      )}

      {/* Scene archetype picker — sticky so it stays visible while scrolling results */}
      <div className="sticky top-0 z-10 mx-auto mb-4 max-w-lg sm:max-w-none rounded-xl bg-[var(--hf-bg)] pb-2 pt-1">
        <p className="mb-2 text-[0.7rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
          Match my scene{sceneArchetypes.length > 0 ? ` · ${sceneArchetypes.length} selected` : ''}
        </p>
        <div className="flex flex-wrap gap-2">
          {(Object.entries(SCENE_ARCHETYPES) as [SceneArchetype, typeof SCENE_ARCHETYPES[SceneArchetype]][]).map(([key, meta]) => {
            const active = sceneArchetypes.includes(key)
            return (
              <button
                key={key}
                type="button"
                onClick={() => toggleArchetype(key)}
                title={meta.desc}
                className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors"
                style={{
                  borderColor: active ? 'var(--hf-primary-1)' : 'var(--hf-border)',
                  background: active ? 'var(--hf-primary-1)' : 'var(--hf-card-bg)',
                  color: active ? '#fff' : 'var(--hf-text-secondary)',
                }}
              >
                <span>{meta.icon}</span>
                <span>{meta.label}</span>
              </button>
            )
          })}
          {sceneArchetypes.length > 0 && (
            <button
              type="button"
              onClick={() => onSceneArchetypesChange([])}
              className="rounded-full border border-[var(--hf-border)] px-3 py-1 text-xs text-[var(--hf-text-tertiary)] transition-colors hover:text-[var(--hf-text-secondary)]"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="mx-auto grid max-w-lg gap-3 sm:max-w-none sm:grid-cols-2">
        {twinRanked.map((r) => (
          <TwinResultCard
            key={r.key}
            query={queryPlace}
            result={r}
            priorities={priorities}
            selectedPillars={selectedPillars}
            selected={selectedTwinKey === r.key}
            showPillarDiffs={selectedTwinKey !== r.key}
            onSelect={() => onSelectTwinResult(selectedTwinKey === r.key ? null : r.key)}
          />
        ))}
      </div>
    </div>
  )
}
