'use client'

import type { CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { VibeTwinResult } from '@/lib/vibeFeatures'
import { VIBE_LABELS, type VibeKey } from '@/lib/vibeFeatures'
import { inferCatalogMetro } from '@/lib/catalogMapTypes'
import MetroDot from '@/components/catalog/MetroDot'

const KEYS: VibeKey[] = ['scene', 'race', 'bach', 'dem', 'scap', 'gvi', 'water']

function DimBar({ label, query, twin }: { label: string; query: number | null | undefined; twin: number | null | undefined }) {
  const q = query ?? 0.5
  const t = twin ?? 0.5
  const diff = Math.round((t - q) * 100)
  const absDiff = Math.abs(diff)
  const color = absDiff <= 6 ? 'var(--hf-text-tertiary)' : diff > 0 ? '#16a34a' : '#dc2626'

  return (
    <div className="flex items-center gap-1.5">
      <span className="w-[72px] shrink-0 text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)] truncate">{label}</span>
      <div className="relative h-1 flex-1 rounded-full bg-[var(--hf-border)]">
        <div
          className="absolute inset-y-0 left-0 rounded-full opacity-30"
          style={{ width: `${q * 100}%`, background: 'var(--hf-primary-1)' }}
        />
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${t * 100}%`, background: 'var(--hf-primary-1)' }}
        />
      </div>
      <span
        className="w-8 shrink-0 text-right text-[0.6rem] font-bold tabular-nums"
        style={{ color }}
      >
        {absDiff <= 6 ? '≈' : diff > 0 ? `+${absDiff}` : `−${absDiff}`}
      </span>
    </div>
  )
}

interface VibeTwinResultCardProps {
  result: VibeTwinResult
  selected?: boolean
  onSelect?: () => void
}

export default function VibeTwinResultCard({ result, selected, onSelect }: VibeTwinResultCardProps) {
  const place = result.place as CatalogMapPlace & { catalog: { type?: string } }
  const metro = inferCatalogMetro(result.place as Parameters<typeof inferCatalogMetro>[0])
  const typeLabel = (place.catalog.type || '').trim()
  const typePretty = typeLabel ? typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1).toLowerCase() : ''
  const hf = typeof result.place.score.total_score === 'number' ? result.place.score.total_score : null

  const qnorm = result.queryFeatures.norm
  const pnorm = result.vibeFeatures.norm

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
          <h3 className="text-sm font-bold text-[var(--hf-text-primary)]">{place.catalog.name}</h3>
          <MetroDot metro={metro} />
        </div>
        <p className="mt-0.5 text-[0.7rem] text-[var(--hf-text-secondary)]">
          {place.catalog.county_borough}, {(place.catalog as { state_abbr?: string }).state_abbr}
          {typePretty ? ` · ${typePretty}` : ''}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span className="rounded px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)] bg-[var(--hf-border)]">
            {result.vibeFeatures.areaType?.replace('_', ' ')}
          </span>
          {result.vibeFeatures.waterType !== 'none' && (
            <span className="rounded px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)] bg-[var(--hf-border)]">
              {result.vibeFeatures.waterType}
            </span>
          )}
          {hf != null && (
            <span className="ml-auto text-[0.65rem] font-semibold text-[var(--hf-text-tertiary)] tabular-nums">
              HF {hf.toFixed(1)}
            </span>
          )}
        </div>
      </div>

      <div className="mt-3 space-y-1.5 border-t border-[var(--hf-border)] pt-2">
        <div className="mb-1 text-[0.6rem] font-bold uppercase tracking-wide text-[var(--hf-text-tertiary)]">
          Vibe dimensions <span className="font-normal opacity-60 ml-1">ghost bar = query</span>
        </div>
        {KEYS.map((k) => (
          <DimBar
            key={k}
            label={VIBE_LABELS[k]}
            query={qnorm[k]}
            twin={pnorm[k]}
          />
        ))}
      </div>
    </div>
  )
}
