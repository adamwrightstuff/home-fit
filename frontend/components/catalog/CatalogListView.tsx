'use client'

import { Fragment, useMemo, useState } from 'react'
import type { PillarPriorities } from '@/components/SearchOptions'
import { getAllCatalogIndexDisplay } from '@/lib/catalogMapGeo'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import {
  catalogRowKey,
  inferCatalogMetro,
  type CatalogMapIndexMode,
  type CatalogMapPlace,
} from '@/lib/catalogMapTypes'
import { catalogRampKey } from '@/lib/catalogIndexColors'
import { scoreBandFill, homefitPillarBarFill, RAMP_HEX } from '@/lib/indexColorSystem'
import { isPillarIndexMode, PILLAR_INDEX_MODES } from '@/lib/catalogMapTypes'
import { PILLAR_META, PILLAR_ORDER } from '@/lib/pillars'
import ArchetypeBadge from '@/components/catalog/ArchetypeBadge'
import TrajectoryChip from '@/components/catalog/TrajectoryChip'
import LocalSceneChip from '@/components/catalog/LocalSceneChip'

const METRO_DOT_COLOR: Record<'nyc' | 'la' | 'sf', string> = { nyc: '#6B5CE7', la: '#E76B5C', sf: '#2A9D8F' }
function MetroDot({ metro }: { metro: 'nyc' | 'la' | 'sf' }) {
  return <span className="inline-block h-2 w-2 rounded-full" style={{ background: METRO_DOT_COLOR[metro] }} title={metro.toUpperCase()} />
}

function ExplorerPillarGrid({ place, priorities }: { place: CatalogMapPlace; priorities: PillarPriorities }) {
  const rw = reweightScoreResponseFromPriorities(place.score, priorities)
  const lp = rw.livability_pillars as unknown as Record<
    string,
    { score?: number; weight?: number; status?: string }
  >
  return (
    <div className="space-y-1 border-t border-[var(--hf-border)] bg-[var(--hf-bg-subtle)] px-2 py-3">
      <div className="mb-2 text-[0.6rem] font-bold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
        Pillars (score · weight in HomeFit blend)
      </div>
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {PILLAR_ORDER.map((k) => {
          const row = lp[k]
          const score =
            row && typeof row.score === 'number' && Number.isFinite(row.score) && row.status !== 'failed'
              ? row.score
              : null
          const w = typeof row?.weight === 'number' && Number.isFinite(row.weight) ? row.weight : 0
          const fill = score != null ? homefitPillarBarFill(score) : 'rgba(0,0,0,0.08)'
          return (
            <div key={k} className="flex min-w-0 items-center gap-2 text-[0.65rem]">
              <span className="w-[7.5rem] shrink-0 truncate text-[var(--hf-text-primary)]" title={PILLAR_META[k].description}>{PILLAR_META[k].name}</span>
              <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
                {score != null && (
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, score)}%`, background: fill }} />
                )}
              </div>
              <span className="w-7 shrink-0 tabular-nums text-[var(--hf-text-secondary)]">
                {score != null ? score.toFixed(0) : '—'}
              </span>
              <span className="w-9 shrink-0 text-right tabular-nums text-[var(--hf-text-tertiary)]">{w.toFixed(0)}%</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

interface CatalogListViewProps {
  places: CatalogMapPlace[]
  priorities: PillarPriorities
  indexMode?: CatalogMapIndexMode
  onTwinRow: (key: string) => void
  compareIds?: string[]
  onCompareToggle?: (key: string) => void
  onRowExpand?: (key: string | null) => void
  /** When set (search mode), keyed by row key — lists filter/dealbreaker labels that exclude the place. */
  filteredOutReasons?: Record<string, string[]>
}

export default function CatalogListView({ places, priorities, indexMode = 'homefit', onTwinRow, compareIds = [], onCompareToggle, onRowExpand, filteredOutReasons }: CatalogListViewProps) {
  const pillarMode = isPillarIndexMode(indexMode)
  const activePillarMeta = pillarMode ? PILLAR_INDEX_MODES.find(p => p.id === indexMode) : null
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  const avgScore = useMemo(() => {
    const scores = places
      .map((p) => reweightScoreResponseFromPriorities(p.score, priorities).total_score)
      .filter((s): s is number => typeof s === 'number' && Number.isFinite(s))
    if (scores.length === 0) return null
    return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
  }, [places, priorities])

  const toggleRow = (key: string) => {
    const next = expandedKey === key ? null : key
    setExpandedKey(next)
    onRowExpand?.(next)
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto px-2 pb-8">
      <table className="w-full border-collapse text-left text-xs">
        <thead className="sticky top-0 z-10 bg-white/95 backdrop-blur">
          <tr className="border-b border-[var(--hf-border)]">
            <th className="py-2 pr-2 font-semibold">Place</th>
            <th className="py-2 px-1"> </th>
            {pillarMode ? (
              <th className="py-2 px-1 font-semibold" colSpan={1} title={activePillarMeta?.label}>{activePillarMeta?.label ?? 'Pillar'}</th>
            ) : (
              <th className="py-2 px-1 font-semibold">
                <abbr title="HomeFit score — weighted composite of all 13 pillars (0–100)" style={{ textDecoration: 'underline dotted', textUnderlineOffset: '2px', cursor: 'help' }}>Score</abbr>
                {avgScore != null && (
                  <span className="ml-1.5 font-normal text-[0.6rem] text-[var(--hf-text-tertiary)]">avg {avgScore}</span>
                )}
              </th>
            )}
            <th className="py-2 px-1 font-semibold">Archetype &amp; Character</th>
            <th className="py-2 pl-1"> </th>
          </tr>
        </thead>
        <tbody>
          {places.map((p, i) => {
            const key = catalogRowKey(p.catalog)
            const failReasons = filteredOutReasons?.[key] ?? []
            const isFilteredOut = failReasons.length > 0
            const prevKey = i > 0 ? catalogRowKey(places[i - 1]!.catalog) : null
            const prevWasPassing = prevKey ? (filteredOutReasons?.[prevKey] ?? []).length === 0 : false
            const showDivider = filteredOutReasons && isFilteredOut && prevWasPassing
            const idx = getAllCatalogIndexDisplay(p, priorities)
            const rw = reweightScoreResponseFromPriorities(p.score, priorities)
            const hf = rw.total_score
            const metro = inferCatalogMetro(p as CatalogMapPlace & { metro?: 'nyc' | 'la' | 'sf' })
            const expanded = expandedKey === key
            const bar = (v: number | null, mode: CatalogMapIndexMode) => {
              if (v == null || !Number.isFinite(v)) return <span className="text-[var(--hf-text-tertiary)]">—</span>
              const ramp = catalogRampKey(
                mode === 'homefit' ? 'homefit' : mode === 'longevity' ? 'longevity' : mode === 'happiness' ? 'happiness' : 'status'
              )
              const fill = scoreBandFill(ramp, v)
              return (
                <div className="flex items-center gap-1">
                  <div className="h-1.5 w-10 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
                    <div className="h-full rounded-full" style={{ width: `${v}%`, background: fill }} />
                  </div>
                  <span className="tabular-nums text-[var(--hf-text-secondary)]">{v.toFixed(0)}</span>
                </div>
              )
            }
            return (
              <Fragment key={key}>
                {showDivider && (
                  <tr>
                    <td colSpan={5} className="py-1.5 px-0">
                      <div className="flex items-center gap-2 text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
                        <div className="h-px flex-1 bg-[var(--hf-border)]" />
                        <span>Outside your filters</span>
                        <div className="h-px flex-1 bg-[var(--hf-border)]" />
                      </div>
                    </td>
                  </tr>
                )}
                <tr
                  className={`group/row cursor-pointer border-b border-[var(--hf-border)] align-top ${
                    expanded ? 'bg-[var(--hf-hover-bg)]' : 'hover:bg-[var(--hf-hover-bg)]'
                  } ${isFilteredOut ? 'opacity-50' : ''}`}
                  onClick={() => toggleRow(key)}
                >
                  <td className="py-2 pr-2">
                    <div className="text-sm font-semibold text-[var(--hf-text-primary)]">{p.catalog.name}</div>
                    <div className="text-[0.6rem] text-[var(--hf-text-tertiary)]">
                      {p.catalog.county_borough}, {p.catalog.state_abbr}
                    </div>
                    {isFilteredOut && (
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        {failReasons.map((r) => (
                          <span key={r} className="rounded-full bg-amber-50 px-1.5 py-px text-[0.55rem] font-semibold text-amber-700 ring-1 ring-inset ring-amber-200">
                            {r}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="py-2 px-1">
                    <MetroDot metro={metro} />
                  </td>
                  {pillarMode ? (() => {
                    const pScore = (p.score.livability_pillars as any)?.[indexMode]?.score ?? null
                    const v = typeof pScore === 'number' && Number.isFinite(pScore) ? pScore : null
                    return (
                      <td className="py-2 px-1">
                        {v == null ? <span className="text-[var(--hf-text-tertiary)]">—</span> : (
                          <span className="text-sm font-bold tabular-nums" style={{ color: RAMP_HEX.teal[400] }}>{v.toFixed(0)}</span>
                        )}
                      </td>
                    )
                  })() : (() => {
                    const compositeV = indexMode === 'longevity' ? idx.longevity : indexMode === 'happiness' ? idx.happiness : null
                    const displayV = compositeV ?? hf
                    const rampKey = indexMode === 'longevity' ? 'longevity' : indexMode === 'happiness' ? 'happiness' : 'homefit'
                    return (
                      <td className="py-2 px-1">
                        <span className="text-sm font-bold tabular-nums" style={{ color: displayV != null ? scoreBandFill(catalogRampKey(rampKey), displayV) : 'var(--hf-text-tertiary)' }}>
                          {displayV != null ? displayV.toFixed(0) : '—'}
                        </span>
                      </td>
                    )
                  })()}
                  <td className="py-2 px-1 align-top">
                    <span style={{ display: 'inline-flex', flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap', whiteSpace: 'nowrap' }}>
                      <ArchetypeBadge
                        archetype={p.score.status_signal_breakdown?.archetype ?? null}
                        breakdown={p.score.status_signal_breakdown ?? null}
                        compositeScore={
                          typeof p.score.status_signal === 'number' ? p.score.status_signal : null
                        }
                        compact
                      />
                      <TrajectoryChip trajectory={p.score.status_signal_breakdown?.trajectory ?? null} compact />
                      <LocalSceneChip bucket={p.score.local_scene_bucket ?? null} compact />
                    </span>
                  </td>
                  <td className="py-2 pl-1">
                    <div className="flex items-center gap-1">
                      {onCompareToggle && (
                        <button
                          type="button"
                          aria-label={`Add ${p.catalog.name} to comparison`}
                          aria-pressed={compareIds.includes(key)}
                          className={`rounded border px-1.5 py-0.5 text-[0.65rem] font-bold opacity-0 transition-opacity group-hover/row:opacity-100 focus:opacity-100 ${
                            compareIds.includes(key) ? 'border-gray-200 text-gray-300' : 'border-gray-200 text-gray-500'
                          }`}
                          disabled={!compareIds.includes(key) && compareIds.length >= 2}
                          title={!compareIds.includes(key) && compareIds.length >= 2 ? 'Max 2 neighborhoods' : undefined}
                          onClick={(e) => { e.stopPropagation(); onCompareToggle(key) }}
                        >
                          {compareIds.includes(key) ? '✓' : 'Compare'}
                        </button>
                      )}
                      <button
                        type="button"
                        className="rounded border border-[var(--hf-border)] px-1.5 py-0.5 text-[0.65rem] font-bold text-[var(--hf-primary-1)]"
                        onClick={(e) => { e.stopPropagation(); onTwinRow(key) }}
                      >
                        Twin →
                      </button>
                    </div>
                  </td>
                </tr>
                {expanded && (
                  <tr className="border-b border-[var(--hf-border)] bg-[var(--hf-bg-subtle)]">
                    <td colSpan={5} className="p-0">
                      {(p.score.local_scene_bucket || p.score.status_signal_breakdown?.llm_summary) && (
                        <div style={{ padding: '0.75rem 1rem 0' }}>
                          {p.score.local_scene_bucket && (
                            <span style={{ fontSize: '0.65rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--hf-text-tertiary)', display: 'block', marginBottom: '0.25rem' }}>
                              {p.score.local_scene_bucket === 'High' ? 'Vibrant scene' : p.score.local_scene_bucket === 'Some' ? 'Some scene' : 'Quiet area'}
                            </span>
                          )}
                          {p.score.status_signal_breakdown?.llm_summary && (
                            <p style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.55, color: 'var(--hf-text-secondary)' }}>
                              {p.score.status_signal_breakdown.llm_summary}
                            </p>
                          )}
                        </div>
                      )}
                      <ExplorerPillarGrid place={p} priorities={priorities} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
