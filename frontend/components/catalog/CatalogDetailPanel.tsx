'use client'

import { X } from 'lucide-react'
import { catalogRowKey, type CatalogMapIndexMode, type CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import { getAllCatalogIndexDisplay, getStandoutPillarChips } from '@/lib/catalogMapGeo'
import { catalogRampKey } from '@/lib/catalogIndexColors'
import {
  STATUS_ARCHETYPE_RAMP,
  fullBreakdownCtaStyle,
  normalizeStatusArchetypeKey,
  statusArchetypeNumeral400,
  statusArchetypeNumeral600,
} from '@/lib/indexColorSystem'
import { getStatusBadgeModel } from '@/lib/statusSignalArchetype'
import { HOMEFIT_COPY, LONGEVITY_COPY, HAPPINESS_INDEX_COPY, STATUS_SIGNAL_COPY } from '@/lib/pillars'

const INDEX_TABS: { id: CatalogMapIndexMode; label: string; tooltip: string }[] = [
  { id: 'homefit', label: 'Trovamo', tooltip: HOMEFIT_COPY.tooltip },
  { id: 'longevity', label: 'Longevity', tooltip: LONGEVITY_COPY.tooltip },
  { id: 'happiness', label: 'Happiness', tooltip: HAPPINESS_INDEX_COPY.tooltip },
  { id: 'status', label: 'Archetype', tooltip: STATUS_SIGNAL_COPY.tooltip },
]

const PEEK_RAMP_CSS: Record<Exclude<CatalogMapIndexMode, 'status'>, { c400: string; c600: string }> = {
  homefit: { c400: 'var(--c-purple-400)', c600: 'var(--c-purple-600)' },
  longevity: { c400: 'var(--c-teal-400)', c600: 'var(--c-teal-600)' },
  happiness: { c400: 'var(--c-blue-400)', c600: 'var(--c-blue-600)' },
}

function fmt(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(1)
}

interface CatalogDetailPanelProps {
  place: CatalogMapPlace | null
  indexMode: CatalogMapIndexMode
  onIndexModeChange: (mode: CatalogMapIndexMode) => void
  priorities: PillarPriorities
  onClose: () => void
  onFullBreakdown: (place: CatalogMapPlace) => void
}

export default function CatalogDetailPanel({
  place,
  indexMode,
  onIndexModeChange,
  priorities,
  onClose,
  onFullBreakdown,
}: CatalogDetailPanelProps) {
  const allIdx = place ? getAllCatalogIndexDisplay(place, priorities) : null
  const chips = place ? getStandoutPillarChips(place, indexMode, priorities) : []
  const archetypeRamp = STATUS_ARCHETYPE_RAMP[normalizeStatusArchetypeKey(allIdx?.archetype)]
  const statusBadge = place
    ? getStatusBadgeModel(
        place.score.status_signal_breakdown ?? null,
        typeof place.score.status_signal === 'number' ? place.score.status_signal : null
      )
    : null
  const breakdownBtn = fullBreakdownCtaStyle(catalogRampKey(indexMode))

  const scoreForTab = (id: CatalogMapIndexMode): number | null => {
    if (!allIdx) return null
    switch (id) {
      case 'homefit': return allIdx.homefit
      case 'longevity': return allIdx.longevity
      case 'happiness': return allIdx.happiness
      case 'status': return allIdx.statusSignal
      default: return null
    }
  }

  const scoreNumeralStyle = (tabId: CatalogMapIndexMode, active: boolean) => {
    if (tabId === 'status') {
      const c600 = statusArchetypeNumeral600(allIdx?.archetype ?? null)
      const c400 = statusArchetypeNumeral400(allIdx?.archetype ?? null)
      return { fontSize: '1.15rem', fontWeight: 700 as const, lineHeight: 1, color: active ? c400 : c600 }
    }
    const { c400, c600 } = PEEK_RAMP_CSS[tabId]
    return { fontSize: '1.15rem', fontWeight: 700 as const, lineHeight: 1, color: active ? c400 : c600 }
  }

  const isOpen = !!place

  return (
    <div
      className="absolute right-0 top-0 bottom-0 z-10 flex flex-col overflow-hidden"
      style={{
        width: 320,
        background: 'var(--hf-card-bg)',
        borderLeft: '1px solid var(--hf-border)',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.08)',
        transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.25s cubic-bezier(0.4,0,0.2,1)',
        pointerEvents: isOpen ? 'auto' : 'none',
      }}
    >
      {/* Header */}
      <div className="flex shrink-0 items-start justify-between gap-2 border-b border-[var(--hf-border)] px-4 py-3">
        {place ? (
          <div className="min-w-0">
            <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--hf-text-primary)', lineHeight: 1.25 }}>
              {place.catalog.name}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--hf-text-secondary)', marginTop: 2 }}>
              {place.catalog.county_borough}, {place.catalog.state_abbr}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: '0.875rem', color: 'var(--hf-text-secondary)' }}>Select a neighborhood</div>
        )}
        <button
          type="button"
          className="shrink-0 rounded-lg p-1.5 text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]"
          onClick={onClose}
          aria-label="Close panel"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {place && (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          {/* Score grid */}
          <div className="mb-3 grid grid-cols-4 rounded-xl border border-[var(--hf-border)] bg-[var(--hf-bg-subtle)]">
            {INDEX_TABS.map((tab) => {
              const active = indexMode === tab.id
              const v = scoreForTab(tab.id)
              return (
                <button
                  key={tab.id}
                  type="button"
                  title={tab.tooltip}
                  onClick={() => onIndexModeChange(tab.id)}
                  className={`flex flex-col items-center py-2.5 px-1 transition-colors ${active ? 'rounded-xl bg-white shadow-sm' : ''}`}
                  style={{ border: 'none', background: active ? '#fff' : 'transparent', cursor: 'pointer' }}
                >
                  <div style={{ fontSize: '0.6rem', letterSpacing: '0.06em', color: 'var(--hf-text-tertiary)', marginBottom: 4, textTransform: 'uppercase' }}>
                    {tab.label}
                  </div>
                  {tab.id !== 'status' ? (
                    <span className="tabular-nums" style={scoreNumeralStyle(tab.id, active)}>{fmt(v)}</span>
                  ) : (
                    <span style={{ fontSize: '0.65rem', fontWeight: 600, color: active ? statusArchetypeNumeral400(allIdx?.archetype ?? null) : statusArchetypeNumeral600(allIdx?.archetype ?? null) }}>
                      {allIdx?.archetype ? allIdx.archetype.split(' ')[0] : '—'}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Archetype badge */}
          {statusBadge ? (
            <div
              className="mb-3 inline-flex max-w-full items-center gap-1.5 rounded-full"
              style={{
                padding: '4px 10px 4px 7px',
                background: statusBadge.variant === 'named' ? archetypeRamp[50] : 'transparent',
                border: statusBadge.variant === 'named' ? '1px solid transparent' : '1px solid rgba(100,116,139,0.4)',
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: statusBadge.variant === 'named' ? archetypeRamp[400] : '#9CA3AF' }} aria-hidden />
              <span style={{ fontSize: '0.75rem', fontWeight: 500, color: archetypeRamp[800] }}>{statusBadge.text}</span>
            </div>
          ) : allIdx?.archetype ? (
            <div
              className="mb-3 inline-flex max-w-full items-center gap-1.5 rounded-full"
              style={{ padding: '4px 10px 4px 7px', background: archetypeRamp[50] }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: archetypeRamp[400] }} aria-hidden />
              <span style={{ fontSize: '0.75rem', fontWeight: 500, color: archetypeRamp[800] }}>{allIdx.archetype}</span>
            </div>
          ) : null}

          {/* Standout pillar chips */}
          {chips.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {chips.map((c) => {
                const isTop = c.tier === 'top'
                return (
                  <span
                    key={`${c.pillarKey}-${c.tier}`}
                    className="inline-flex items-baseline gap-1"
                    style={{
                      fontSize: '0.7rem',
                      padding: '3px 9px',
                      borderRadius: 20,
                      ...(isTop
                        ? { background: 'var(--c-teal-50)', border: '0.5px solid var(--c-teal-200)', color: 'var(--c-teal-800)' }
                        : { background: 'var(--c-coral-50)', border: '0.5px solid var(--c-coral-200)', color: 'var(--c-coral-800)' }),
                    }}
                  >
                    <span className="truncate">{c.name}</span>
                    <span className="shrink-0 tabular-nums font-semibold">{c.score.toFixed(0)}</span>
                  </span>
                )
              })}
            </div>
          )}

          {/* Summary */}
          {place.score.place_summary && (
            <p style={{ margin: '0 0 16px', fontSize: '0.8rem', lineHeight: 1.6, color: 'var(--hf-text-secondary)' }}>
              {place.score.place_summary}
            </p>
          )}

          {/* CTA */}
          <button
            type="button"
            className="w-full rounded-xl py-2.5 text-center text-sm font-bold"
            style={{ background: breakdownBtn.background, color: breakdownBtn.color }}
            onClick={() => onFullBreakdown(place)}
          >
            Full breakdown →
          </button>
        </div>
      )}
    </div>
  )
}

export function findPlaceByKey(places: CatalogMapPlace[], key: string | null): CatalogMapPlace | null {
  if (!key) return null
  return places.find((p) => catalogRowKey(p.catalog) === key) ?? null
}
