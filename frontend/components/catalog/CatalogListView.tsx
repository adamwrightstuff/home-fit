'use client'

import { Fragment, useState } from 'react'
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
import { scoreBandFill, homefitPillarBarFill } from '@/lib/indexColorSystem'
import { PILLAR_META, PILLAR_ORDER } from '@/lib/pillars'

function MetroDot({ metro }: { metro: 'nyc' | 'la' }) {
  const c = metro === 'nyc' ? '#6B5CE7' : '#E76B5C'
  return <span className="inline-block h-2 w-2 rounded-full" style={{ background: c }} title={metro.toUpperCase()} />
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
              <span className="w-[7.5rem] shrink-0 truncate text-[var(--hf-text-primary)]">{PILLAR_META[k].name}</span>
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
  onTwinRow: (key: string) => void
}

export default function CatalogListView({ places, priorities, onTwinRow }: CatalogListViewProps) {
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  const toggleRow = (key: string) => {
    setExpandedKey((cur) => (cur === key ? null : key))
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto px-2 pb-8">
      <table className="w-full border-collapse text-left text-xs">
        <thead className="sticky top-0 z-10 bg-white/95 backdrop-blur">
          <tr className="border-b border-[var(--hf-border)]">
            <th className="py-2 pr-2 font-semibold">Place</th>
            <th className="py-2 px-1"> </th>
            <th className="py-2 px-1 font-semibold">HF</th>
            <th className="py-2 px-1 font-semibold">Lon</th>
            <th className="py-2 px-1 font-semibold">Hap</th>
            <th className="py-2 px-1 font-semibold">Stat</th>
            <th className="py-2 pl-1"> </th>
          </tr>
        </thead>
        <tbody>
          {places.map((p) => {
            const key = catalogRowKey(p.catalog)
            const idx = getAllCatalogIndexDisplay(p, priorities)
            const rw = reweightScoreResponseFromPriorities(p.score, priorities)
            const hf = rw.total_score
            const metro = inferCatalogMetro(p as CatalogMapPlace & { metro?: 'nyc' | 'la' })
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
                <tr
                  className={`cursor-pointer border-b border-[var(--hf-border)] align-top ${
                    expanded ? 'bg-[var(--hf-hover-bg)]' : ''
                  }`}
                  onClick={() => toggleRow(key)}
                >
                  <td className="py-2 pr-2">
                    <div className="font-semibold text-[var(--hf-text-primary)]">{p.catalog.name}</div>
                    <div className="text-[0.65rem] text-[var(--hf-text-secondary)]">
                      {p.catalog.county_borough}, {p.catalog.state_abbr}
                    </div>
                  </td>
                  <td className="py-2 px-1">
                    <MetroDot metro={metro} />
                  </td>
                  <td className="py-2 px-1">{bar(hf, 'homefit')}</td>
                  <td className="py-2 px-1">{bar(idx.longevity, 'longevity')}</td>
                  <td className="py-2 px-1">{bar(idx.happiness, 'happiness')}</td>
                  <td className="py-2 px-1">{bar(idx.statusSignal, 'status')}</td>
                  <td className="py-2 pl-1">
                    <button
                      type="button"
                      className="rounded border border-[var(--hf-border)] px-1.5 py-0.5 text-[0.65rem] font-bold text-[var(--hf-primary-1)]"
                      onClick={(e) => {
                        e.stopPropagation()
                        onTwinRow(key)
                      }}
                    >
                      Twin →
                    </button>
                  </td>
                </tr>
                {expanded && (
                  <tr className="border-b border-[var(--hf-border)] bg-[var(--hf-bg-subtle)]">
                    <td colSpan={7} className="p-0">
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
