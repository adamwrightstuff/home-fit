'use client'

import { useRef, useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { fullBreakdownCtaStyle } from '@/lib/indexColorSystem'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'
import PillarInfoIcon from '@/components/PillarInfoIcon'
import type { PillarPriorities, PriorityLevel } from '@/components/SearchOptions'

const GROUPS: { title: string; keys: PillarKey[] }[] = [
  {
    title: 'Lifestyle',
    keys: ['natural_beauty', 'active_outdoors', 'neighborhood_amenities'],
  },
  {
    title: 'Community',
    keys: ['social_fabric', 'diversity', 'quality_education', 'community_safety'],
  },
  {
    title: 'Practicality',
    keys: ['public_transit_access', 'healthcare_access', 'air_travel_access', 'housing_value'],
  },
  {
    title: 'Economics',
    keys: ['economic_opportunity', 'climate_risk'],
  },
]

const LEVELS: PriorityLevel[] = ['None', 'Low', 'Medium', 'High']

interface CatalogWeightPanelProps {
  open: boolean
  onClose: () => void
  priorities: PillarPriorities
  onChange: (next: PillarPriorities) => void
  onTakeQuiz?: () => void
  householdIncome?: number | null
  incomeInputValue?: string
  onIncomeInputChange?: (v: string) => void
  onIncomeBlur?: () => void
  onIncomeClear?: () => void
  /** Current home monthly cost (mortgage + tax) — overrides area median for the matched place. */
  currentHomeMonthlyCostInput?: string
  onCurrentHomeMonthlyCostInputChange?: (v: string) => void
  onCurrentHomeMonthlyCostBlur?: () => void
  onCurrentHomeMonthlyCostClear?: () => void
  /** The confirmed selected place name for the current home. */
  currentHomeMatch?: string
  /** Called with the exact catalog place name when user selects from the dropdown. */
  onCurrentHomeSelect?: (name: string) => void
  /** Options for the current home dropdown — pass catalog places as { name, sub }. */
  currentHomePlaceOptions?: { name: string; sub: string }[]
  /** Deal-breaker pillars (currently housing_value only). Independent of importance weight. */
  dealbreakers?: Partial<Record<PillarKey, boolean>>
  onDealbreakerToggle?: (key: PillarKey) => void
}

/** Pillars with a deal-breaker gate wired up. Independent axis from importance — see housing_value MVP. */
const DEALBREAKER_PILLARS: PillarKey[] = ['housing_value', 'air_travel_access', 'quality_education', 'community_safety', 'neighborhood_amenities', 'healthcare_access', 'active_outdoors', 'climate_risk', 'social_fabric']

/**
 * Human-readable statement of what "fails" means per dealbreaker pillar — mirrors the exact
 * thresholds in lib/reweight.ts's passesXDealbreaker functions. Keep these in sync if a
 * threshold changes.
 */
const DEALBREAKER_DESCRIPTIONS: Partial<Record<PillarKey, string>> = {
  housing_value: 'Exclude places where home price exceeds 3x your household income',
  air_travel_access: 'Exclude places more than 60 min drive from an airport',
  quality_education: 'Exclude places with school ratings below 3-star equivalent',
  community_safety: 'Exclude places less safe than typical for the area type',
  neighborhood_amenities: 'Exclude places with poor access to daily amenities — combines street-level walkability and town center vibrancy',
  healthcare_access: 'Exclude places with below-average access to hospitals and clinics',
  active_outdoors: 'Exclude places with limited trails, parks, or outdoor recreation',
  climate_risk: 'Exclude places with below-average climate safety (flood, heat, fire exposure)',
  social_fabric: 'Exclude places with weak community cohesion scores',
}

export default function CatalogWeightPanel({ open, onClose, priorities, onChange, onTakeQuiz, householdIncome, incomeInputValue = '', onIncomeInputChange, onIncomeBlur, onIncomeClear, currentHomeMonthlyCostInput = '', onCurrentHomeMonthlyCostInputChange, onCurrentHomeMonthlyCostBlur, onCurrentHomeMonthlyCostClear, currentHomeMatch = '', onCurrentHomeSelect, currentHomePlaceOptions = [], dealbreakers, onDealbreakerToggle }: CatalogWeightPanelProps) {
  const [comboInput, setComboInput] = useState(currentHomeMatch)
  const [comboOpen, setComboOpen] = useState(false)
  const comboRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!currentHomeMatch) setComboInput('')
  }, [currentHomeMatch])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (comboRef.current && !comboRef.current.contains(e.target as Node)) setComboOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const comboFiltered = comboInput.trim()
    ? currentHomePlaceOptions.filter(o => o.name.toLowerCase().includes(comboInput.toLowerCase())).slice(0, 8)
    : currentHomePlaceOptions.slice(0, 8)

  if (!open) return null

  function setLevel(key: PillarKey, level: PriorityLevel) {
    onChange({ ...priorities, [key]: level })
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
            <div className="flex items-center gap-2 font-bold text-[var(--hf-text-primary)]">
              Weights
            </div>
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
                      <div className="mb-1 flex items-center gap-1 text-xs font-medium text-[var(--hf-text-primary)]">
                        <span>{meta.icon} {meta.name}</span>
                        <PillarInfoIcon pillarKey={key} />
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
                      {DEALBREAKER_PILLARS.includes(key) && (
                        <label className="mt-2 flex items-start gap-2 text-xs font-medium text-[var(--hf-text-primary)]">
                          <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={Boolean(dealbreakers?.[key])}
                            onChange={() => onDealbreakerToggle?.(key)}
                          />
                          <span>
                            🚫 Deal breaker
                            <span className="block font-normal text-[var(--hf-text-secondary)]">
                              {DEALBREAKER_DESCRIPTIONS[key]}
                            </span>
                          </span>
                        </label>
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

            {householdIncome && onCurrentHomeMonthlyCostInputChange && (
              <div className="mt-3 rounded-lg border border-dashed border-[var(--hf-border)] p-2.5">
                <div className="mb-2 text-xs font-medium text-[var(--hf-text-secondary)]">
                  Current home override
                  <span
                    className="ml-1 inline-flex h-4 w-4 cursor-default items-center justify-center rounded-full border border-[var(--hf-border)] text-[0.65rem] font-bold text-[var(--hf-text-secondary)]"
                    title="When set, your current home's housing score is computed from your actual monthly cost instead of the area median price. All other places still use area median."
                  >
                    ?
                  </span>
                </div>
                <div className="mb-2" ref={comboRef}>
                  <div className="mb-1 text-[0.65rem] uppercase tracking-wide text-[var(--hf-text-tertiary)]">Neighborhood</div>
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Search your neighborhood…"
                      value={comboInput}
                      onChange={(e) => { setComboInput(e.target.value); setComboOpen(true) }}
                      onFocus={() => setComboOpen(true)}
                      className="w-full rounded-lg border border-[var(--hf-border)] px-2 py-1.5 pr-6 text-xs"
                    />
                    {currentHomeMatch && (
                      <button
                        type="button"
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--hf-text-tertiary)] hover:text-[var(--hf-text-secondary)]"
                        onClick={() => { setComboInput(''); onCurrentHomeSelect?.('') }}
                        aria-label="Clear neighborhood"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    )}
                    {comboOpen && comboFiltered.length > 0 && (
                      <ul className="absolute bottom-full z-50 mb-0.5 max-h-48 w-full overflow-y-auto rounded-lg border border-[var(--hf-border)] bg-[var(--hf-surface)] py-1 shadow-lg">
                        {comboFiltered.map((o) => (
                          <li key={o.name}>
                            <button
                              type="button"
                              className="flex w-full flex-col px-2.5 py-1.5 text-left hover:bg-[var(--hf-track)]"
                              onMouseDown={(e) => {
                                e.preventDefault()
                                setComboInput(o.name)
                                setComboOpen(false)
                                onCurrentHomeSelect?.(o.name)
                              }}
                            >
                              <span className="text-xs font-medium text-[var(--hf-text-primary)]">{o.name}</span>
                              <span className="text-[0.65rem] text-[var(--hf-text-tertiary)]">{o.sub}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-[0.65rem] uppercase tracking-wide text-[var(--hf-text-tertiary)]">Monthly cost (mortgage + tax)</div>
                  <div className="relative flex items-center">
                    <span className="absolute left-2 text-xs text-[var(--hf-text-secondary)]">$</span>
                    <input
                      type="text"
                      inputMode="numeric"
                      placeholder="monthly"
                      value={currentHomeMonthlyCostInput}
                      onChange={(e) => onCurrentHomeMonthlyCostInputChange(e.target.value)}
                      onBlur={onCurrentHomeMonthlyCostBlur}
                      className="w-full rounded-lg border border-[var(--hf-border)] py-1.5 pl-5 pr-8 text-xs"
                    />
                    {currentHomeMonthlyCostInput && onCurrentHomeMonthlyCostClear && (
                      <button
                        type="button"
                        className="absolute right-2 text-[var(--hf-text-tertiary)] hover:text-[var(--hf-text-secondary)]"
                        onClick={onCurrentHomeMonthlyCostClear}
                        aria-label="Clear monthly cost"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
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
