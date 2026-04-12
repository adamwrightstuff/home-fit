'use client'

import { X } from 'lucide-react'
import { PILLAR_META, PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import { defaultTwinPillarSet } from '@/lib/twinSimilarity'

const MIN_PILLARS = 2

interface PillarTwinDrawerProps {
  open: boolean
  onClose: () => void
  selected: Set<PillarKey>
  onChange: (next: Set<PillarKey>) => void
  /** When true, checkboxes are non-interactive (Twin Finder state 1). */
  disabled?: boolean
}

export default function PillarTwinDrawer({
  open,
  onClose,
  selected,
  onChange,
  disabled = false,
}: PillarTwinDrawerProps) {
  if (!open) return null

  const count = selected.size
  const toggle = (k: PillarKey) => {
    if (disabled) return
    const n = new Set(selected)
    if (n.has(k)) {
      if (n.size <= MIN_PILLARS) return
      n.delete(k)
    } else {
      n.add(k)
    }
    onChange(n)
  }

  const selectAll = () => {
    if (disabled) return
    onChange(new Set(PILLAR_ORDER))
  }

  const resetDefault = () => {
    if (disabled) return
    onChange(defaultTwinPillarSet())
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-end bg-black/40 sm:items-start sm:justify-end sm:pt-16"
      role="dialog"
      aria-modal="true"
      aria-label="Twin matching pillars"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-t-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] shadow-[var(--hf-card-shadow)] sm:mr-4 sm:max-h-[calc(100vh-4rem)] sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--hf-border)] px-4 py-3">
          <div>
            <div className="font-bold text-[var(--hf-text-primary)]">Twin pillars</div>
            <p className="text-xs text-[var(--hf-text-secondary)]">
              {count} of {PILLAR_ORDER.length} pillars · Minimum {MIN_PILLARS}
            </p>
          </div>
          <button
            type="button"
            className="rounded-lg p-2 text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
          <div className="mb-1 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={disabled}
              className="text-xs font-semibold text-[var(--hf-primary-1)] disabled:opacity-40"
              onClick={resetDefault}
            >
              Reset to default
            </button>
            <button
              type="button"
              disabled={disabled}
              className="text-xs font-semibold text-[var(--hf-primary-1)] disabled:opacity-40"
              onClick={selectAll}
            >
              Select all
            </button>
          </div>
          <ul className="space-y-1.5">
            {PILLAR_ORDER.map((k) => (
              <li key={k}>
                <label
                  className={`flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-[var(--hf-hover-bg)] ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
                >
                  <input
                    type="checkbox"
                    disabled={disabled}
                    checked={selected.has(k)}
                    onChange={() => toggle(k)}
                    className="rounded border-[var(--hf-border-strong)]"
                  />
                  <span className="text-sm text-[var(--hf-text-primary)]">
                    {PILLAR_META[k].icon} {PILLAR_META[k].name}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </div>
        <div className="border-t border-[var(--hf-border)] px-4 py-3">
          <button
            type="button"
            className="w-full rounded-xl py-2.5 text-sm font-bold text-white"
            style={{ background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' }}
            onClick={onClose}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
