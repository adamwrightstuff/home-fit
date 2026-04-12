'use client'

import { PILLAR_META, type PillarKey } from '@/lib/pillars'

export type DiffRow = { key: PillarKey; diff: number }

/** Pillar name | proportional bar | ±value (bar width = abs(diff)/100 of track). */
export default function TwinDiffRows({
  rows,
  variant = 'default',
}: {
  rows: DiffRow[]
  variant?: 'default' | 'muted'
}) {
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.diff)))

  return (
    <div className={`space-y-2 ${variant === 'muted' ? 'opacity-70' : ''}`}>
      {rows.map((d) => {
        const abs = Math.abs(d.diff)
        const barColor =
          d.diff > 5 ? '#1D9E75' : d.diff < -5 ? '#E76B5C' : 'rgba(100,100,100,0.45)'
        const pct = (abs / maxAbs) * 100
        return (
          <div key={d.key} className="flex items-center gap-2 text-[0.75rem]">
            <span className="w-[7.5rem] shrink-0 truncate text-[var(--hf-text-primary)]">
              {PILLAR_META[d.key].name}
            </span>
            <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
              <div
                className="h-full rounded-full transition-[width]"
                style={{
                  width: `${Math.min(100, pct)}%`,
                  background: barColor,
                  maxWidth: '100%',
                }}
              />
            </div>
            <span className="w-11 shrink-0 tabular-nums text-right text-[var(--hf-text-secondary)]">
              {d.diff > 0 ? '+' : ''}
              {d.diff.toFixed(0)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
