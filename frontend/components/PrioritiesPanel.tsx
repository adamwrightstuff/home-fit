'use client'

import Link from 'next/link'
import { X } from 'lucide-react'
import { fullBreakdownCtaStyle } from '@/lib/indexColorSystem'
import { PILLAR_META } from '@/lib/pillars'
import PillarInfoIcon from '@/components/PillarInfoIcon'
import { DEFAULT_PRIORITIES, type PillarPriorities, type PriorityLevel } from '@/components/SearchOptions'
import { GROUPS, LEVELS, PERSONAL_ROWS } from '@/components/catalog/fitOptions'

/**
 * Priorities only: how much each pillar matters, for the single-place score page. The catalog uses FitPanel, which
 * adds requirements (what hides places) next to these.
 */
export default function PrioritiesPanel({ open, onClose, priorities, onChange }: {
  open: boolean
  onClose: () => void
  priorities: PillarPriorities
  onChange: (next: PillarPriorities) => void
}) {
  if (!open) return null
  const levelButtons = (key: string) => {
    const current = ((priorities as unknown as Record<string, PriorityLevel | undefined>)[key] ?? 'None') as PriorityLevel
    return (
      <div className="flex flex-wrap gap-1">
        {LEVELS.map((lv) => (
          <button
            key={lv}
            type="button"
            className={`rounded-lg px-2 py-1 text-xs font-semibold transition-colors ${current === lv ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
            style={current === lv ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : undefined}
            onClick={() => onChange({ ...priorities, [key]: lv } as PillarPriorities)}
          >
            {lv}
          </button>
        ))}
      </div>
    )
  }
  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-end bg-black/40 sm:items-start sm:justify-end sm:pt-16"
      role="dialog"
      aria-modal="true"
      aria-label="Pillar importance"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-t-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] shadow-[var(--hf-card-shadow)] sm:mr-4 sm:max-h-[calc(100vh-4rem)] sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--hf-border)] px-4 py-3">
          <div>
            <div className="font-bold text-[var(--hf-text-primary)]">Priorities</div>
            <p className="m-0 text-xs text-[var(--hf-text-secondary)]">Priorities change which places rank higher. Nothing is hidden.</p>
            {JSON.stringify(priorities) !== JSON.stringify(DEFAULT_PRIORITIES) && (
              <button
                type="button"
                onClick={() => onChange({ ...DEFAULT_PRIORITIES })}
                className="mt-1 block text-xs font-semibold"
                style={{ color: 'var(--hf-primary-1)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
              >
                Reset priorities
              </button>
            )}
          </div>
          <button type="button" className="rounded-lg p-2 text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]" onClick={onClose} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
          {GROUPS.map((g) => (
            <details key={g.title} className="mb-3 rounded-xl border border-[var(--hf-border)]" open>
              <summary className="cursor-pointer select-none px-3 py-2 text-sm font-bold text-[var(--hf-text-primary)]">{g.title}</summary>
              <div className="space-y-3 border-t border-[var(--hf-border)] px-2 pb-3 pt-2">
                {g.keys.map((key) => {
                  const meta = PILLAR_META[key]
                  return (
                    <div key={key}>
                      <div className="mb-1 flex items-center gap-1 text-xs font-medium text-[var(--hf-text-primary)]">
                        <span>{meta.icon} {meta.name}</span>
                        <PillarInfoIcon pillarKey={key} />
                      </div>
                      {levelButtons(key)}
                    </div>
                  )
                })}
              </div>
            </details>
          ))}

          <details className="mb-3 rounded-xl border border-[var(--hf-border)]" open>
            <summary className="cursor-pointer select-none px-3 py-2 text-sm font-bold text-[var(--hf-text-primary)]">Personal fit</summary>
            <div className="space-y-3 border-t border-[var(--hf-border)] px-2 pb-3 pt-2">
              {PERSONAL_ROWS.map((row) => (
                <p key={row.key} className="m-0 text-xs text-[var(--hf-text-secondary)]">
                  {row.icon} {row.needs}{' '}
                  <Link href="/profile" className="font-semibold text-[var(--hf-primary-1)]">Open your profile</Link>
                </p>
              ))}
            </div>
          </details>
        </div>

        <div className="border-t border-[var(--hf-border)] px-4 py-3">
          <button type="button" className="w-full rounded-xl py-2.5 text-sm font-bold" style={fullBreakdownCtaStyle('purple')} onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
