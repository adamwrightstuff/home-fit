'use client'

import { X } from 'lucide-react'
import { fullBreakdownCtaStyle } from '@/lib/indexColorSystem'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'
import type { PillarPriorities, PriorityLevel } from '@/components/SearchOptions'
import { NB_PREFERENCE_LABELS, type NbPreference } from '@/lib/nbPreference'

const GROUPS: { title: string; keys: PillarKey[] }[] = [
  {
    title: 'Lifestyle',
    keys: ['neighborhood_beauty', 'active_outdoors', 'neighborhood_amenities'],
  },
  {
    title: 'Community',
    keys: ['social_fabric', 'diversity', 'quality_education', 'community_safety', 'political_lean'],
  },
  {
    title: 'Practicality',
    keys: ['public_transit_access', 'healthcare_access', 'air_travel_access', 'housing_value'],
  },
  {
    title: 'Economics',
    keys: ['economic_security', 'climate_risk'],
  },
]

const LEVELS: PriorityLevel[] = ['None', 'Low', 'Medium', 'High']

interface CatalogWeightPanelProps {
  open: boolean
  onClose: () => void
  priorities: PillarPriorities
  onChange: (next: PillarPriorities) => void
  politicalPreference?: 'progressive' | 'conservative' | null
  onPoliticalPreferenceChange?: (pref: 'progressive' | 'conservative' | null) => void
  nbPreference?: NbPreference | null
  onNbPreferenceChange?: (pref: NbPreference | null) => void
  onTakeQuiz?: () => void
  householdIncome?: number | null
  incomeInputValue?: string
  onIncomeInputChange?: (v: string) => void
  onIncomeBlur?: () => void
  onIncomeClear?: () => void
  /** Deal-breaker pillars (currently housing_value only). Independent of importance weight. */
  dealbreakers?: Partial<Record<PillarKey, boolean>>
  onDealbreakerToggle?: (key: PillarKey) => void
}

/** Pillars with a deal-breaker gate wired up. Independent axis from importance — see housing_value MVP. */
const DEALBREAKER_PILLARS: PillarKey[] = ['housing_value']

export default function CatalogWeightPanel({ open, onClose, priorities, onChange, politicalPreference, onPoliticalPreferenceChange, nbPreference, onNbPreferenceChange, onTakeQuiz, householdIncome, incomeInputValue = '', onIncomeInputChange, onIncomeBlur, onIncomeClear, dealbreakers, onDealbreakerToggle }: CatalogWeightPanelProps) {
  if (!open) return null

  function setLevel(key: PillarKey, level: PriorityLevel) {
    onChange({ ...priorities, [key]: level })
    if (key === 'political_lean' && level === 'None') {
      onPoliticalPreferenceChange?.(null)
    }
    if (key === 'neighborhood_beauty' && level === 'None') {
      onNbPreferenceChange?.(null)
    }
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
            <div className="font-bold text-[var(--hf-text-primary)]">Weights</div>
            <p className="text-xs text-[var(--hf-text-secondary)]">
              Scores reflect equal weighting — adjust importance to personalize.
            </p>
            {onTakeQuiz && (
              <button
                type="button"
                onClick={onTakeQuiz}
                className="mt-1.5 text-xs font-semibold"
                style={{ color: 'var(--hf-primary-1)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
              >
                Not sure what matters to you? Take the quiz →
              </button>
            )}
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

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
          {GROUPS.map((g) => (
            <details key={g.title} className="mb-3 rounded-xl border border-[var(--hf-border)]" open>
              <summary className="cursor-pointer select-none px-3 py-2 text-sm font-bold text-[var(--hf-text-primary)]">
                {g.title}
              </summary>
              <div className="space-y-3 border-t border-[var(--hf-border)] px-2 pb-3 pt-2">
                {g.keys.map((key) => {
                  const meta = PILLAR_META[key]
                  const current = priorities[key]
                  return (
                    <div key={key}>
                      <div className="mb-1 text-xs font-medium text-[var(--hf-text-primary)]">
                        {meta.icon} {meta.name}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {LEVELS.map((lv) => (
                          <button
                            key={lv}
                            type="button"
                            className={`rounded-lg px-2 py-1 text-xs font-semibold transition-colors ${
                              current === lv
                                ? 'text-white'
                                : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'
                            }`}
                            style={
                              current === lv
                                ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' }
                                : undefined
                            }
                            onClick={() => setLevel(key, lv)}
                          >
                            {lv}
                          </button>
                        ))}
                      </div>
                      {key === 'neighborhood_beauty' && current !== 'None' && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {(Object.keys(NB_PREFERENCE_LABELS) as NbPreference[]).map((pref) => (
                            <button
                              key={pref}
                              type="button"
                              className={`rounded-lg px-2 py-1 text-xs font-semibold transition-colors ${
                                nbPreference === pref
                                  ? 'text-white'
                                  : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'
                              }`}
                              style={
                                nbPreference === pref
                                  ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' }
                                  : undefined
                              }
                              onClick={() => onNbPreferenceChange?.(nbPreference === pref ? null : pref)}
                            >
                              {NB_PREFERENCE_LABELS[pref]}
                            </button>
                          ))}
                        </div>
                      )}
                      {DEALBREAKER_PILLARS.includes(key) && (
                        <label className="mt-2 flex items-center gap-2 text-xs font-medium text-[var(--hf-text-primary)]">
                          <input
                            type="checkbox"
                            checked={Boolean(dealbreakers?.[key])}
                            onChange={() => onDealbreakerToggle?.(key)}
                          />
                          🚫 Deal breaker — exclude places that fail this
                        </label>
                      )}
                      {key === 'political_lean' && current !== 'None' && (
                        <div className="mt-2 flex gap-1">
                          {(['progressive', 'conservative'] as const).map((pref) => (
                            <button
                              key={pref}
                              type="button"
                              className={`rounded-lg px-2 py-1 text-xs font-semibold transition-colors ${
                                politicalPreference === pref
                                  ? 'text-white'
                                  : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'
                              }`}
                              style={
                                politicalPreference === pref
                                  ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' }
                                  : undefined
                              }
                              onClick={() => onPoliticalPreferenceChange?.(politicalPreference === pref ? null : pref)}
                            >
                              {pref === 'progressive' ? '🔵 Progressive' : '🔴 Conservative'}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </details>
          ))}
        </div>

        {onIncomeInputChange && (
          <div className="border-t border-[var(--hf-border)] px-4 py-3">
            <div className="mb-2 text-xs font-bold text-[var(--hf-text-primary)]">Personalize scores</div>
            <div>
              <div className="mb-1 flex items-center gap-1 text-xs font-medium text-[var(--hf-text-primary)]">
                Household income
                <span
                  className="inline-flex h-4 w-4 cursor-default items-center justify-center rounded-full border border-[var(--hf-border)] text-[0.65rem] font-bold text-[var(--hf-text-secondary)]"
                  title="Used to calculate housing affordability in the Housing Value score. Has no effect on other pillars. Leave blank to use local median income."
                >
                  ?
                </span>
              </div>
              <div className="relative flex items-center">
                <span className="absolute left-2 text-xs text-[var(--hf-text-secondary)]">$</span>
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="annual household"
                  value={incomeInputValue}
                  onChange={(e) => onIncomeInputChange(e.target.value)}
                  onBlur={onIncomeBlur}
                  className="w-full rounded-lg border border-[var(--hf-border)] py-1.5 pl-5 pr-8 text-xs"
                />
                {householdIncome && onIncomeClear && (
                  <button
                    type="button"
                    className="absolute right-2 text-[var(--hf-text-tertiary)] hover:text-[var(--hf-text-secondary)]"
                    onClick={onIncomeClear}
                    aria-label="Clear income"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="border-t border-[var(--hf-border)] px-4 py-3">
          <button
            type="button"
            className="w-full rounded-xl py-2.5 text-sm font-bold"
            style={fullBreakdownCtaStyle('purple')}
            onClick={onClose}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
