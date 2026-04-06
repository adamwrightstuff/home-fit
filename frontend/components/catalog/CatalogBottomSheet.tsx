'use client'

import { catalogRowKey, type CatalogMapIndexMode, type CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import {
  getAllCatalogIndexDisplay,
  getStandoutPillarChips,
} from '@/lib/catalogMapGeo'
import { catalogRampKey } from '@/lib/catalogIndexColors'
import { RAMP_HEX, fullBreakdownCtaStyle } from '@/lib/indexColorSystem'

export type CatalogSheetSnap = 'peek' | 'expanded'

const INDEX_TABS: { id: CatalogMapIndexMode; label: string }[] = [
  { id: 'homefit', label: 'HomeFit' },
  { id: 'longevity', label: 'Longevity' },
  { id: 'happiness', label: 'Happiness' },
  { id: 'status', label: 'Status' },
]

/** Fixed ramp-600 / ramp-400 for catalog peek strip (per design spec). */
const INDEX_PEEK_COLORS: Record<CatalogMapIndexMode, { c400: string; c600: string }> = {
  homefit: { c400: RAMP_HEX.purple[400], c600: RAMP_HEX.purple[600] },
  longevity: { c400: RAMP_HEX.teal[400], c600: RAMP_HEX.teal[600] },
  happiness: { c400: RAMP_HEX.blue[400], c600: RAMP_HEX.blue[600] },
  status: { c400: RAMP_HEX.coral[400], c600: RAMP_HEX.coral[600] },
}

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

  const breakdownBtn = fullBreakdownCtaStyle(catalogRampKey(indexMode))

  return (
    <div
      className="fixed left-0 right-0 z-20 flex flex-col rounded-t-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] shadow-[var(--hf-card-shadow)]"
      style={{
        bottom: 0,
        maxHeight: snap === 'expanded' ? `${expanded_vh}vh` : undefined,
        transition: 'max-height 0.28s ease',
        paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))',
      }}
    >
      <button
        type="button"
        className="flex w-full shrink-0 flex-col border-b border-[var(--hf-border)]"
        onClick={() => onSnapChange(snap === 'peek' ? 'expanded' : 'peek')}
        aria-expanded={snap === 'expanded'}
        aria-label={snap === 'peek' ? 'Expand details' : 'Collapse details'}
      >
        <div
          className="mx-auto"
          style={{
            width: 36,
            paddingTop: 12,
            marginBottom: 12,
          }}
        >
          <div
            style={{
              width: 36,
              height: 4,
              borderRadius: 2,
              background: 'var(--color-border-primary)',
            }}
          />
        </div>
      </button>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-2 pt-0 sm:px-4">
        {!place ? (
          <p className="py-2 text-center text-sm text-[var(--hf-text-secondary)]">Tap a bubble to see scores.</p>
        ) : (
          <>
            <div className="mb-2 flex items-start justify-between gap-3">
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

            <div className="mb-2 grid grid-cols-4 gap-0 py-2">
              {INDEX_TABS.map((tab) => {
                const active = indexMode === tab.id
                const v = scoreForTab(tab.id)
                const { c400, c600 } = INDEX_PEEK_COLORS[tab.id]
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => onIndexModeChange(tab.id)}
                    className="flex flex-col items-center text-center"
                  >
                    <div
                      className="font-normal uppercase"
                      style={{
                        fontSize: 10,
                        letterSpacing: '0.05em',
                        color: 'var(--color-text-tertiary)',
                      }}
                    >
                      {tab.label}
                    </div>
                    <span
                      className="mt-0.5 inline-block tabular-nums leading-none"
                      style={{
                        fontSize: 22,
                        fontWeight: 500,
                        color: active ? c400 : c600,
                        borderBottom: active ? `2px solid ${c400}` : '2px solid transparent',
                      }}
                    >
                      {fmt(v)}
                    </span>
                  </button>
                )
              })}
            </div>

            {allIdx?.archetypeBadge ? (
              <div
                className="mb-2 inline-flex max-w-full self-start items-center rounded-[20px] text-xs font-medium leading-tight"
                style={{
                  gap: 6,
                  background: '#FAECE7',
                  padding: '4px 10px 4px 6px',
                  color: '#712B13',
                }}
              >
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: '#D85A30' }} aria-hidden />
                <span className="min-w-0">
                  {allIdx.archetypeBadge}
                  {place.score.status_signal_breakdown?.signal_strength_label ? (
                    <span style={{ color: '#993C1D' }}>
                      {'  '}
                      {place.score.status_signal_breakdown.signal_strength_label}
                    </span>
                  ) : null}
                </span>
              </div>
            ) : allIdx?.archetype ? (
              <div
                className="mb-2 inline-flex max-w-full self-start items-center rounded-[20px] text-xs font-medium leading-tight"
                style={{
                  gap: 6,
                  background: '#FAECE7',
                  padding: '4px 10px 4px 6px',
                  color: '#712B13',
                }}
              >
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: '#D85A30' }} aria-hidden />
                <span className="min-w-0">{allIdx.archetype}</span>
              </div>
            ) : (
              <p className="mb-2 text-xs text-[var(--hf-text-tertiary)]">No archetype in snapshot</p>
            )}

            {chips.length > 0 && (
              <div className="mb-1 flex flex-wrap gap-2">
                {chips.map((c) => {
                  const isTop = c.tier === 'top'
                  const dotColor = isTop ? RAMP_HEX.teal[400] : RAMP_HEX.coral[400]
                  return (
                    <span
                      key={`${c.pillarKey}-${c.tier}`}
                      className="inline-flex max-w-full items-baseline gap-1.5 rounded-lg bg-[var(--hf-hover-bg)] px-2.5 py-1.5 text-xs font-semibold text-[var(--hf-text-secondary)]"
                      style={{
                        border: '1px solid var(--hf-border)',
                      }}
                    >
                      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: dotColor }} aria-hidden />
                      <span className="truncate">{c.name}</span>
                      <span className="tabular-nums font-extrabold text-[var(--hf-text-secondary)]">
                        {c.score.toFixed(0)}
                      </span>
                    </span>
                  )
                })}
              </div>
            )}

            <button
              type="button"
              className="mt-4 inline-flex w-full items-center justify-center rounded-xl px-4 py-3 text-center text-sm font-bold"
              style={{ background: breakdownBtn.background, color: breakdownBtn.color }}
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
