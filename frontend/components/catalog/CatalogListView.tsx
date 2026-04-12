'use client'

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
import { scoreBandFill } from '@/lib/indexColorSystem'

function MetroDot({ metro }: { metro: 'nyc' | 'la' }) {
  const c = metro === 'nyc' ? '#6B5CE7' : '#E76B5C'
  return <span className="inline-block h-2 w-2 rounded-full" style={{ background: c }} title={metro.toUpperCase()} />
}

interface CatalogListViewProps {
  places: CatalogMapPlace[]
  priorities: PillarPriorities
  onTwinRow: (key: string) => void
}

export default function CatalogListView({ places, priorities, onTwinRow }: CatalogListViewProps) {
  return (
    <div className="min-h-0 flex-1 overflow-auto px-2 pb-28">
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
              <tr key={key} className="border-b border-[var(--hf-border)] align-top">
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
                    onClick={() => onTwinRow(key)}
                  >
                    Twin →
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
