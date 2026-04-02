'use client'

import { ChevronUp } from 'lucide-react'
import { catalogRowKey, type CatalogMapIndexMode, type CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import {
  getAllCatalogIndexDisplay,
  getStandoutPillarChips,
} from '@/lib/catalogMapGeo'
import { CATALOG_INDEX_COLORS } from '@/lib/catalogIndexColors'

export type CatalogSheetSnap = 'peek' | 'expanded'

const INDEX_TABS: { id: CatalogMapIndexMode; label: string; color: string }[] = [
  { id: 'homefit', label: 'HomeFit', color: CATALOG_INDEX_COLORS.homefit },
  { id: 'longevity', label: 'Longevity', color: CATALOG_INDEX_COLORS.longevity },
  { id: 'happiness', label: 'Happiness', color: CATALOG_INDEX_COLORS.happiness },
  { id: 'status', label: 'Status', color: CATALOG_INDEX_COLORS.status },
]

function fmt(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(1)
}

interface CatalogBottomSheetProps {
  place: CatalogMapPlace | null
  indexMode: CatalogMapIndexMode
  onIndexModeChange: (mode: CatalogMapIndexMode) => void
  priorities: PillarPriorities
  snap: CatalogSheetSnap
  onSnapChange: (s: CatalogSheetSnap) => void
  onClose: () => void
  onFullBreakdown: (place: CatalogMapPlace) => void
}

export default function CatalogBottomSheet({
  place,
  indexMode,
  onIndexModeChange,
  priorities,
  snap,
  onSnapChange,
  onClose,
  onFullBreakdown,
}: CatalogBottomSheetProps) {
  const expanded_vh = 58
  const peek_max_px = 380

  const allIdx = place ? getAllCatalogIndexDisplay(place, priorities) : null
  const chips = place ? getStandoutPillarChips(place, indexMode, priorities) : []

  const scoreForTab = (id: CatalogMapIndexMode): number | null => {
    if (!allIdx) return null
    switch (id) {
      case 'homefit':
        return allIdx.homefit
      case 'longevity':
        return allIdx.longevity
      case 'happiness':
        return allIdx.happiness
      case 'status':
        return allIdx.statusSignal
      default:
        return null
    }
  }

  return (
    <div
      className="fixed left-0 right-0 z-20 flex flex-col rounded-t-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] shadow-[var(--hf-card-shadow)]"
      style={{
        bottom: 0,
        maxHeight: snap === 'expanded' ? `${expanded_vh}vh` : peek_max_px,
        transition: 'max-height 0.28s ease',
        paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))',
      }}
    >
      {/* Gestural handle only */}
      <button
        type="button"
        className="flex w-full shrink-0 items-center justify-center border-b border-[var(--hf-border)] py-2.5 text-[var(--hf-text-secondary)]"
        onClick={() => onSnapChange(snap === 'peek' ? 'expanded' : 'peek')}
        aria-expanded={snap === 'expanded'}
        aria-label={snap === 'peek' ? 'Expand details' : 'Collapse details'}
      >
        <ChevronUp
          className="h-5 w-5 shrink-0 transition-transform opacity-70"
          style={{ transform: snap === 'expanded' ? 'rotate(180deg)' : 'none' }}
        />
      </button>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3 pt-2 sm:px-4">
        {!place ? (
          <p className="py-2 text-center text-sm text-[var(--hf-text-secondary)]">Tap a bubble to see scores.</p>
        ) : (
          <>
            {/* Title row + Clear */}
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-lg font-extrabold leading-tight text-[var(--hf-text-primary)]">
                  {place.catalog.name}
                </div>
                <div className="mt-0.5 text-sm text-[var(--hf-text-secondary)]">
                  {place.catalog.county_borough}, {place.catalog.state_abbr}
                </div>
              </div>
              <button
                type="button"
                className="shrink-0 rounded-lg border border-[var(--hf-border)] bg-[var(--hf-hover-bg)] px-3 py-1.5 text-xs font-bold text-[var(--hf-text-primary)]"
                onClick={onClose}
              >
                Clear
              </button>
            </div>

            {/* Four indices — full signal at peek; active tab bordered */}
            <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {INDEX_TABS.map((tab) => {
                const active = indexMode === tab.id
                const v = scoreForTab(tab.id)
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => onIndexModeChange(tab.id)}
                    className="rounded-xl px-2 py-2 text-left transition-[box-shadow,border-color] sm:px-2.5"
                    style={{
                      borderWidth: 2,
                      borderStyle: 'solid',
                      borderColor: active ? tab.color : 'transparent',
                      background: active ? `${tab.color}14` : 'rgba(0,0,0,0.04)',
                      boxShadow: active ? `0 0 0 1px ${tab.color}40` : 'none',
                    }}
                  >
                    <div
                      className="text-[0.65rem] font-bold uppercase tracking-wide opacity-90"
                      style={{ color: tab.color }}
                    >
                      {tab.label}
                    </div>
                    <div
                      className="mt-0.5 text-xl font-extrabold tabular-nums leading-none"
                      style={{ color: tab.color }}
                    >
                      {fmt(v)}
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Archetype — always visible when we have any label */}
            {allIdx?.archetypeBadge ? (
              <div
                className="mb-3 rounded-full px-3 py-1.5 text-center text-xs font-semibold"
                style={{
                  background: `${CATALOG_INDEX_COLORS.status}18`,
                  color: CATALOG_INDEX_COLORS.status,
                  border: `1px solid ${CATALOG_INDEX_COLORS.status}55`,
                }}
              >
                {allIdx.archetypeBadge}
              </div>
            ) : allIdx?.archetype ? (
              <div
                className="mb-3 rounded-full px-3 py-1.5 text-center text-xs font-semibold"
                style={{
                  background: `${CATALOG_INDEX_COLORS.status}18`,
                  color: CATALOG_INDEX_COLORS.status,
                  border: `1px solid ${CATALOG_INDEX_COLORS.status}55`,
                }}
              >
                {allIdx.archetype}
              </div>
            ) : (
              <div
                className="mb-3 rounded-full px-3 py-1.5 text-center text-xs font-medium text-[var(--hf-text-secondary)]"
                style={{
                  background: 'rgba(0,0,0,0.05)',
                  border: '1px solid var(--hf-border)',
                }}
              >
                No archetype in snapshot
              </div>
            )}

            {/* Standout chips */}
            {chips.length > 0 && (
              <div className="mb-1 flex flex-wrap gap-2">
                {chips.map((c) => {
                  const isTop = c.tier === 'top'
                  const base = isTop ? CATALOG_INDEX_COLORS.longevity : CATALOG_INDEX_COLORS.status
                  return (
                    <span
                      key={`${c.pillarKey}-${c.tier}`}
                      className="inline-flex max-w-full items-baseline gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold"
                      style={{
                        background: isTop ? `${base}1f` : `${base}24`,
                        border: `1px solid ${isTop ? `${base}55` : `${base}66`}`,
                        color: 'var(--hf-text-primary)',
                      }}
                    >
                      <span className="truncate" style={{ color: base }}>
                        {c.name}
                      </span>
                      <span className="tabular-nums font-extrabold" style={{ color: base }}>
                        {c.score.toFixed(0)}
                      </span>
                    </span>
                  )
                })}
              </div>
            )}

            <button
              type="button"
              className="mt-4 inline-flex w-full items-center justify-center rounded-xl px-4 py-3 text-center text-sm font-bold text-white"
              style={{ background: 'var(--hf-primary-gradient)' }}
              onClick={() => onFullBreakdown(place)}
            >
              Full breakdown
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export function findPlaceByKey(places: CatalogMapPlace[], key: string | null): CatalogMapPlace | null {
  if (!key) return null
  return places.find((p) => catalogRowKey(p.catalog) === key) ?? null
}
