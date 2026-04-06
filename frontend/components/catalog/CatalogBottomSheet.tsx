'use client'

import { catalogRowKey, type CatalogMapIndexMode, type CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { PillarPriorities } from '@/components/SearchOptions'
import {
  getAllCatalogIndexDisplay,
  getStandoutPillarChips,
} from '@/lib/catalogMapGeo'
import { catalogRampKey } from '@/lib/catalogIndexColors'
import {
  STATUS_ARCHETYPE_RAMP,
  fullBreakdownCtaStyle,
  normalizeStatusArchetypeKey,
  statusArchetypeNumeral400,
  statusArchetypeNumeral600,
} from '@/lib/indexColorSystem'

export type CatalogSheetSnap = 'peek' | 'expanded'

const INDEX_TABS: { id: CatalogMapIndexMode; label: string }[] = [
  { id: 'homefit', label: 'HomeFit' },
  { id: 'longevity', label: 'Longevity' },
  { id: 'happiness', label: 'Happiness' },
  { id: 'status', label: 'Status' },
]

/** CSS token pairs for peek score strip (non–Status Signal indices). */
const PEEK_RAMP_CSS: Record<
  Exclude<CatalogMapIndexMode, 'status'>,
  { c400: string; c600: string }
> = {
  homefit: { c400: 'var(--c-purple-400)', c600: 'var(--c-purple-600)' },
  longevity: { c400: 'var(--c-teal-400)', c600: 'var(--c-teal-600)' },
  happiness: { c400: 'var(--c-blue-400)', c600: 'var(--c-blue-600)' },
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
  const archetypeRamp = STATUS_ARCHETYPE_RAMP[normalizeStatusArchetypeKey(allIdx?.archetype)]

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

  const scoreNumeralStyle = (tabId: CatalogMapIndexMode, active: boolean) => {
    if (tabId === 'status') {
      const c600 = statusArchetypeNumeral600(allIdx?.archetype ?? null)
      const c400 = statusArchetypeNumeral400(allIdx?.archetype ?? null)
      const color = active ? c400 : c600
      return {
        fontSize: '1.1rem',
        fontWeight: 600 as const,
        lineHeight: 1,
        color,
        textDecorationLine: active ? ('underline' as const) : ('none' as const),
        textDecorationThickness: active ? 2 : undefined,
        textDecorationColor: active ? c400 : undefined,
        textUnderlineOffset: active ? 2 : undefined,
      }
    }
    const { c400, c600 } = PEEK_RAMP_CSS[tabId]
    const color = active ? c400 : c600
    return {
      fontSize: '1.1rem',
      fontWeight: 600 as const,
      lineHeight: 1,
      color,
      textDecorationLine: active ? ('underline' as const) : ('none' as const),
      textDecorationThickness: active ? 2 : undefined,
      textDecorationColor: active ? c400 : undefined,
      textUnderlineOffset: active ? 2 : undefined,
    }
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
        aria-label={snap === 'peek' ? 'Expand details' : 'Collapse details'}
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

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!place ? (
          <p className="py-2 text-center text-[0.8rem] text-[var(--hf-text-secondary)]">Tap a bubble to see scores.</p>
        ) : (
          <>
            <div
              className="flex items-start justify-between gap-3"
              style={{ marginBottom: 8 }}
            >
              <div className="min-w-0">
                <div
                  style={{
                    fontSize: '1rem',
                    fontWeight: 600,
                    color: 'var(--hf-text-primary)',
                    lineHeight: 1.2,
                    margin: 0,
                  }}
                >
                  {place.catalog.name}
                </div>
                <div
                  style={{
                    fontSize: '0.8rem',
                    color: 'var(--hf-text-secondary)',
                    margin: 0,
                  }}
                >
                  {place.catalog.county_borough}, {place.catalog.state_abbr}
                </div>
              </div>
              <button
                type="button"
                className="shrink-0 rounded-lg border border-[var(--hf-border)] bg-[var(--hf-hover-bg)] px-3 py-1.5 font-bold text-[var(--hf-text-primary)]"
                style={{ fontSize: '0.8rem' }}
                onClick={onClose}
              >
                Clear
              </button>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                marginBottom: 8,
              }}
            >
              {INDEX_TABS.map((tab) => {
                const active = indexMode === tab.id
                const v = scoreForTab(tab.id)
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => onIndexModeChange(tab.id)}
                    style={{
                      textAlign: 'center',
                      padding: '4px 0',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    <div
                      style={{
                        fontSize: '0.65rem',
                        letterSpacing: '0.06em',
                        color: 'var(--hf-text-tertiary)',
                        marginBottom: 2,
                        textTransform: 'uppercase',
                      }}
                    >
                      {tab.label}
                    </div>
                    <span className="tabular-nums" style={scoreNumeralStyle(tab.id, active)}>
                      {fmt(v)}
                    </span>
                  </button>
                )
              })}
            </div>

            {allIdx?.archetypeBadge ? (
              <div
                className="max-w-full self-start"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  borderRadius: 20,
                  padding: '3px 8px 3px 6px',
                  marginBottom: 8,
                  background: archetypeRamp[50],
                }}
              >
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    flexShrink: 0,
                    background: archetypeRamp[400],
                  }}
                  aria-hidden
                />
                <span
                  className="min-w-0"
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 500,
                    color: archetypeRamp[800],
                  }}
                >
                  {allIdx.archetypeBadge}
                  {place.score.status_signal_breakdown?.signal_strength_label ? (
                    <span style={{ color: archetypeRamp[600] }}>
                      {'  '}
                      {place.score.status_signal_breakdown.signal_strength_label}
                    </span>
                  ) : null}
                </span>
              </div>
            ) : allIdx?.archetype ? (
              <div
                className="max-w-full self-start"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  borderRadius: 20,
                  padding: '3px 8px 3px 6px',
                  marginBottom: 8,
                  background: archetypeRamp[50],
                }}
              >
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    flexShrink: 0,
                    background: archetypeRamp[400],
                  }}
                  aria-hidden
                />
                <span
                  className="min-w-0"
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 500,
                    color: archetypeRamp[800],
                  }}
                >
                  {allIdx.archetype}
                </span>
              </div>
            ) : (
              <p className="mb-2 text-[0.7rem] text-[var(--hf-text-tertiary)]">No archetype in snapshot</p>
            )}

            {chips.length > 0 && (
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 5,
                  marginBottom: 10,
                }}
              >
                {chips.map((c) => {
                  const isTop = c.tier === 'top'
                  return (
                    <span
                      key={`${c.pillarKey}-${c.tier}`}
                      className="inline-flex max-w-full min-w-0 items-baseline gap-1"
                      style={{
                        fontSize: '0.7rem',
                        padding: '2px 8px',
                        borderRadius: 20,
                        ...(isTop
                          ? {
                              background: 'var(--c-teal-50)',
                              border: '0.5px solid var(--c-teal-200)',
                              color: 'var(--c-teal-800)',
                            }
                          : {
                              background: 'var(--c-coral-50)',
                              border: '0.5px solid var(--c-coral-200)',
                              color: 'var(--c-coral-800)',
                            }),
                      }}
                    >
                      <span className="truncate">{c.name}</span>
                      <span className="shrink-0 tabular-nums font-semibold">{c.score.toFixed(0)}</span>
                    </span>
                  )
                })}
              </div>
            )}

            <button
              type="button"
              className="inline-flex w-full items-center justify-center rounded-xl text-center font-bold"
              style={{
                padding: '10px 16px',
                fontSize: '0.85rem',
                background: breakdownBtn.background,
                color: breakdownBtn.color,
              }}
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
