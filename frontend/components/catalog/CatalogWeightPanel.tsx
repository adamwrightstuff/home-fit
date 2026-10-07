'use client'

import Link from 'next/link'
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

type PersonalKey = 'commute_time' | 'social_connection'
const PERSONAL_ROWS: { key: PersonalKey; icon: string; name: string; needs: string }[] = [
  { key: 'commute_time', icon: '🚆', name: 'Your commute', needs: 'Add a work hub to weigh your commute.' },
  { key: 'social_connection', icon: '💛', name: 'Closeness to people you know', needs: 'Add people you want to live near to weigh this.' },
]

interface CatalogWeightPanelProps {
  open: boolean
  onClose: () => void
  priorities: PillarPriorities
  onChange: (next: PillarPriorities) => void
  onTakeQuiz?: () => void
  /** Profile facts, shown read-only; they're edited on the profile page. */
  householdIncome?: number | null
  currentHomeName?: string
  currentHomeMonthlyCost?: number | null
  /** Personal-fit weights only apply once the profile gives them something to measure. */
  hasWorkHub?: boolean
  hasPeople?: boolean
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
  community_safety: "Exclude places in the highest-crime quarter nationally (more crime than where 75% of Americans live)",
  neighborhood_amenities: 'Exclude places with poor access to daily amenities — combines street-level walkability and town center vibrancy',
  healthcare_access: 'Exclude places with below-average access to hospitals and clinics',
  active_outdoors: 'Exclude places with limited trails, parks, or outdoor recreation',
  climate_risk: 'Exclude places with below-average climate safety (flood, heat, fire exposure)',
  social_fabric: 'Exclude places with weak community cohesion scores',
}

export default function CatalogWeightPanel({ open, onClose, priorities, onChange, onTakeQuiz, householdIncome, currentHomeName = '', currentHomeMonthlyCost, hasWorkHub = false, hasPeople = false, dealbreakers, onDealbreakerToggle }: CatalogWeightPanelProps) {
  if (!open) return null

  function setLevel(key: PillarKey, level: PriorityLevel) {
    onChange({ ...priorities, [key]: level })
  }

  function setPersonalLevel(key: PersonalKey, level: PriorityLevel) {
    onChange({ ...priorities, [key]: level } as PillarPriorities)
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

          <details className="mb-3 rounded-xl border border-[var(--hf-border)]" open>
            <summary className="cursor-pointer select-none px-3 py-2 text-sm font-bold text-[var(--hf-text-primary)]">
              Personal fit
            </summary>
            <div className="space-y-3 border-t border-[var(--hf-border)] px-2 pb-3 pt-2">
              <p className="text-[0.7rem] leading-snug text-[var(--hf-text-secondary)]">
                Based on your profile. Rough estimates, not one of the research-backed pillars above.
              </p>
              {PERSONAL_ROWS.map((row) => {
                const available = row.key === 'commute_time' ? hasWorkHub : hasPeople
                const current = (priorities as unknown as Record<string, PriorityLevel | undefined>)[row.key] ?? 'None'
                return (
                  <div key={row.key}>
                    <div className="mb-1 text-xs font-medium text-[var(--hf-text-primary)]">
                      {row.icon} {row.name}
                    </div>
                    {available ? (
                      <div className="flex flex-wrap gap-1">
                        {LEVELS.map((lv) => (
                          <button
                            key={lv}
                            type="button"
                            className={`rounded-lg px-2 py-1 text-xs font-semibold transition-colors ${
                              current === lv ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'
                            }`}
                            style={current === lv ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : undefined}
                            onClick={() => setPersonalLevel(row.key, lv)}
                          >
                            {lv}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="m-0 text-xs text-[var(--hf-text-tertiary)]">
                        {row.needs}{' '}
                        <Link href="/profile" className="font-semibold text-[var(--hf-primary-1)]">
                          Open your profile
                        </Link>
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </details>
        </div>

        <div className="border-t border-[var(--hf-border)] px-4 py-3 text-xs text-[var(--hf-text-secondary)]">
          <div className="mb-1 font-bold text-[var(--hf-text-primary)]">Your profile</div>
          {householdIncome || currentHomeName ? (
            <div>
              {householdIncome ? `$${householdIncome.toLocaleString('en-US')} household income` : null}
              {householdIncome && currentHomeName ? ' · ' : null}
              {currentHomeName
                ? `lives in ${currentHomeName}${currentHomeMonthlyCost ? ` ($${currentHomeMonthlyCost.toLocaleString('en-US')}/mo)` : ''}`
                : null}
            </div>
          ) : (
            <div>Add your income and where you live now to personalize housing affordability.</div>
          )}
          <Link href="/profile" className="mt-1 inline-block font-semibold text-[var(--hf-primary-1)]">
            Edit your profile
          </Link>
        </div>

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
