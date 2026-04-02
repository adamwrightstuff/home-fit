'use client'

import Link from 'next/link'
import { ChevronUp } from 'lucide-react'
import { catalogRowKey, type CatalogMapIndexMode, type CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import { displayIndexValue, topPillarCallouts } from '@/lib/catalogMapGeo'

export type CatalogSheetSnap = 'peek' | 'expanded'

interface CatalogBottomSheetProps {
  place: CatalogMapPlace | null
  indexMode: CatalogMapIndexMode
  priorities: PillarPriorities
  snap: CatalogSheetSnap
  onSnapChange: (s: CatalogSheetSnap) => void
  onClose: () => void
}

export default function CatalogBottomSheet({
  place,
  indexMode,
  priorities,
  snap,
  onSnapChange,
  onClose,
}: CatalogBottomSheetProps) {
  const peek_h = 96
  const expanded_vh = 42

  const idx = place ? displayIndexValue(place, indexMode, priorities) : null
  const callouts = place ? topPillarCallouts(place, indexMode, priorities, 2) : []

  const resultsHref = place
    ? `/results?location=${encodeURIComponent(place.catalog.search_query)}`
    : '#'

  return (
    <div
      className="fixed left-0 right-0 z-20 flex flex-col rounded-t-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] shadow-[var(--hf-card-shadow)]"
      style={{
        bottom: 0,
        maxHeight: snap === 'expanded' ? `${expanded_vh}vh` : peek_h,
        transition: 'max-height 0.28s ease',
        paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))',
      }}
    >
      <button
        type="button"
        className="flex w-full flex-col items-center gap-1 border-b border-[var(--hf-border)] py-2 text-[var(--hf-text-secondary)]"
        onClick={() => onSnapChange(snap === 'peek' ? 'expanded' : 'peek')}
        aria-expanded={snap === 'expanded'}
      >
        <ChevronUp
          className="h-5 w-5 shrink-0 transition-transform"
          style={{ transform: snap === 'expanded' ? 'rotate(180deg)' : 'none' }}
        />
        <span className="text-xs font-semibold uppercase tracking-wide">Neighborhood</span>
      </button>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-3 pt-1">
        {!place ? (
          <p className="text-center text-sm text-[var(--hf-text-secondary)]">Tap a bubble to see scores.</p>
        ) : snap === 'peek' ? (
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="font-bold text-[var(--hf-text-primary)]">{place.catalog.name}</div>
              <div className="text-xs text-[var(--hf-text-secondary)]">
                {place.catalog.county_borough}, {place.catalog.state_abbr}
              </div>
            </div>
            {idx && (
              <div className="text-right">
                <div className="text-xs text-[var(--hf-text-secondary)]">{idx.label}</div>
                <div className="text-xl font-extrabold tabular-nums text-[var(--hf-text-primary)]">{idx.value}</div>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="text-lg font-bold text-[var(--hf-text-primary)]">{place.catalog.name}</h2>
                <p className="text-sm text-[var(--hf-text-secondary)]">
                  {place.catalog.county_borough}, {place.catalog.state_abbr}
                </p>
              </div>
              <button
                type="button"
                className="text-sm font-semibold text-[var(--hf-primary-1)]"
                onClick={onClose}
              >
                Clear
              </button>
            </div>

            {idx && (
              <div
                className="rounded-xl border border-[var(--hf-border)] px-3 py-2"
                style={{ background: 'rgba(102, 126, 234, 0.06)' }}
              >
                <div className="text-xs font-semibold text-[var(--hf-text-secondary)]">{idx.label}</div>
                <div className="text-2xl font-extrabold tabular-nums" style={{ color: 'var(--hf-text-primary)' }}>
                  {idx.value}
                </div>
                {idx.sub ? <div className="mt-1 text-xs text-[var(--hf-text-secondary)]">{idx.sub}</div> : null}
              </div>
            )}

            {callouts.length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--hf-text-secondary)]">
                  Standouts
                </div>
                <ul className="mt-1 list-inside list-disc text-sm text-[var(--hf-text-primary)]">
                  {callouts.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            <Link
              href={resultsHref}
              className="inline-flex w-full items-center justify-center rounded-xl px-4 py-3 text-center text-sm font-bold text-white"
              style={{ background: 'var(--hf-primary-gradient)' }}
            >
              Full breakdown
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}

export function findPlaceByKey(places: CatalogMapPlace[], key: string | null): CatalogMapPlace | null {
  if (!key) return null
  return places.find((p) => catalogRowKey(p.catalog) === key) ?? null
}
