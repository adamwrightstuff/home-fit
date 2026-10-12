'use client'

import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronDown, MapPin, Search, X } from 'lucide-react'
import { CATALOG_METROS, CATALOG_METRO_META, type CatalogMetro } from '@/lib/catalogMetros'

type MetroValue = 'all' | CatalogMetro

interface MetroPickerProps {
  value: MetroValue
  onChange: (v: MetroValue) => void
  counts?: Record<CatalogMetro, number> | null
}

/** Single-button metro selector that opens a searchable bottom sheet; scales to any number of metros. */
export default function MetroPicker({ value, onChange, counts }: MetroPickerProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!open) { setQuery(''); return }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [open])

  const options = useMemo(() => {
    const q = query.trim().toLowerCase()
    return CATALOG_METROS
      .filter((m) => !q || CATALOG_METRO_META[m].longLabel.toLowerCase().includes(q) || CATALOG_METRO_META[m].label.toLowerCase().includes(q))
      .sort((a, b) => (counts?.[b] ?? 0) - (counts?.[a] ?? 0))
  }, [query, counts])

  const total = counts ? CATALOG_METROS.reduce((s, m) => s + counts[m], 0) : null
  const triggerLabel = value === 'all' ? 'All metros' : CATALOG_METRO_META[value].longLabel
  const pick = (v: MetroValue) => { onChange(v); setOpen(false) }

  const row = (key: string, selected: boolean, label: string, count: number | null, color: string | null, v: MetroValue) => (
    <li key={key}>
      <button
        type="button"
        onClick={() => pick(v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm active:bg-[var(--hf-hover-bg)]"
      >
        {color ? (
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color }} aria-hidden />
        ) : (
          <MapPin className="h-3.5 w-3.5 shrink-0 text-[var(--hf-text-tertiary)]" aria-hidden />
        )}
        <span className={`flex-1 ${selected ? 'font-semibold' : ''}`}>{label}</span>
        {count !== null && <span className="text-xs text-[var(--hf-text-tertiary)]">{count}</span>}
        {selected && <Check className="h-4 w-4" style={{ color: 'var(--hf-primary-1)' }} aria-hidden />}
      </button>
    </li>
  )

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        className="flex w-full items-center gap-2 rounded-full border border-[var(--hf-border)] bg-white px-3 py-2 text-sm font-semibold text-[var(--hf-text-primary)] shadow-sm"
      >
        <MapPin className="h-4 w-4 shrink-0" style={{ color: 'var(--hf-primary-1)' }} aria-hidden />
        <span className="flex-1 truncate text-left">{triggerLabel}</span>
        <ChevronDown className="h-4 w-4 shrink-0 text-[var(--hf-text-tertiary)]" aria-hidden />
      </button>

      {open && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-end" role="dialog" aria-modal="true" aria-label="Choose metro">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="relative flex max-h-[80dvh] w-full flex-col rounded-t-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between px-4 pb-2 pt-4">
              <h2 className="text-base font-bold">Choose a metro</h2>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="p-1 text-[var(--hf-text-tertiary)]">
                <X className="h-5 w-5" />
              </button>
            </div>
            {CATALOG_METROS.length > 6 && (
              <div className="px-4 pb-2">
                <div className="flex items-center gap-2 rounded-lg bg-[var(--hf-hover-bg)] px-3 py-2">
                  <Search className="h-4 w-4 text-[var(--hf-text-tertiary)]" aria-hidden />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search metros"
                    className="w-full bg-transparent text-base outline-none"
                  />
                </div>
              </div>
            )}
            <ul className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-[env(safe-area-inset-bottom)]">
              {!query.trim() && row('all', value === 'all', 'All metros', total, null, 'all')}
              {options.map((m) => row(m, value === m, CATALOG_METRO_META[m].longLabel, counts ? counts[m] : null, CATALOG_METRO_META[m].color, m))}
              {options.length === 0 && <li className="px-4 py-6 text-center text-sm text-[var(--hf-text-tertiary)]">No matching metros</li>}
            </ul>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
