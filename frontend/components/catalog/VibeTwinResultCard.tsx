'use client'

import type { VibeTwinResult } from '@/lib/vibeFeatures'
import { VIBE_LABELS, type VibeKey } from '@/lib/vibeFeatures'
import { inferCatalogMetro } from '@/lib/catalogMapTypes'
import MetroDot from '@/components/catalog/MetroDot'

const KEYS: VibeKey[] = ['scene', 'race', 'bach', 'dem', 'scap', 'gvi', 'water']

interface VibeTwinResultCardProps {
  result: VibeTwinResult
  selected?: boolean
  onSelect?: () => void
}

export default function VibeTwinResultCard({ result, selected, onSelect }: VibeTwinResultCardProps) {
  const place = result.place
  const metro = inferCatalogMetro(place as Parameters<typeof inferCatalogMetro>[0])
  const catalog = place.catalog as { name: string; county_borough?: string; state_abbr?: string; type?: string }
  const typeLabel = (catalog.type || '').trim()
  const typePretty = typeLabel ? typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1).toLowerCase() : ''
  const hf = typeof place.score.total_score === 'number' ? place.score.total_score : null

  const qraw = result.queryFeatures.raw
  const praw = result.vibeFeatures.raw

  const diffs = KEYS.map((k) => {
    const q = qraw[k] ?? 50
    const p = praw[k] ?? 50
    return { key: k, diff: Math.round(p - q) }
  })

  const maxAbs = Math.max(1, ...diffs.map((d) => Math.abs(d.diff)))

  return (
    <div
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onClick={onSelect}
      onKeyDown={onSelect ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect() } } : undefined}
      className={`relative rounded-2xl border bg-[var(--hf-card-bg)] p-3 shadow-[var(--hf-card-shadow-sm)] ${
        selected ? 'border-[var(--hf-primary-1)] ring-2 ring-[var(--hf-primary-1)]/25' : 'border-[var(--hf-border)]'
      } ${onSelect ? 'cursor-pointer transition hover:bg-[var(--hf-hover-bg)]' : ''}`}
    >
      <div className="absolute right-3 top-3 text-2xl font-bold tabular-nums" style={{ color: '#6B5CE7' }}>
        {result.matchPct}%
      </div>

      <div className="pr-16">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-[var(--hf-text-primary)]">{catalog.name}</h3>
          <MetroDot metro={metro} />
        </div>
        <p className="mt-0.5 text-[0.7rem] text-[var(--hf-text-secondary)]">
          {catalog.county_borough}, {catalog.state_abbr}
          {typePretty ? ` · ${typePretty}` : ''}
        </p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
            HomeFit
          </span>
          <span className="text-lg font-bold tabular-nums" style={{ color: '#6B5CE7' }}>
            {hf != null ? hf.toFixed(1) : '—'}
          </span>
        </div>
      </div>

      <div className="mt-3 border-t border-[var(--hf-border)] pt-2">
        <div className="mb-1.5 text-[0.6rem] font-bold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
          Vibe dimensions
        </div>
        <div className="space-y-2">
          {diffs.map(({ key, diff }) => {
            const abs = Math.abs(diff)
            const barColor = diff > 5 ? '#1D9E75' : diff < -5 ? '#E76B5C' : 'rgba(100,100,100,0.45)'
            const pct = (abs / maxAbs) * 100
            return (
              <div key={key} className="flex items-center gap-2 text-[0.75rem]">
                <span className="w-[7.5rem] shrink-0 truncate text-[var(--hf-text-primary)]">
                  {VIBE_LABELS[key]}
                </span>
                <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
                  <div
                    className="h-full rounded-full transition-[width]"
                    style={{ width: `${Math.min(100, pct)}%`, background: barColor }}
                  />
                </div>
                <span className="w-11 shrink-0 tabular-nums text-right text-[var(--hf-text-secondary)]">
                  {diff > 0 ? '+' : ''}{diff === 0 ? '0' : diff}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
