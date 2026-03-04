'use client'

import React, { useMemo, useState, useCallback, useEffect, useRef } from 'react'
import { ArrowLeft, ChevronLeft, RefreshCcw, Search } from 'lucide-react'
import type { PillarPriorities, PriorityLevel } from './SearchOptions'
import AppHeader from './AppHeader'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

const PILLAR_ORDER: PillarKey[] = [
  'natural_beauty',
  'built_beauty',
  'access_to_nature',
  'neighborhood_amenities',
  'active_outdoors',
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'economic_security',
  'quality_education',
  'housing_value',
  'climate_risk',
  'social_fabric',
]

const TOTAL_QUESTIONS = 5

const QUESTIONS = [
  {
    id: 'life_stage',
    type: 'single' as const,
    prompt: 'What best describes your household right now?',
    options: [
      { value: 'single_couple', text: 'Single or couple, no kids' },
      { value: 'family_young', text: 'Family with young kids' },
      { value: 'family_older', text: 'Family with older kids / teens' },
      { value: 'empty_nester', text: 'Empty nester or retired' },
      { value: 'flexible', text: 'Flexible — things will change soon' },
    ],
  },
  {
    id: 'weekend_energy',
    type: 'single' as const,
    prompt: "On a free weekend, you're most likely to be—",
    options: [
      { value: 'outdoors', text: 'Outside — hiking, biking, on the water' },
      { value: 'neighborhood', text: 'Exploring the neighborhood' },
      { value: 'home_social', text: 'At home or with close friends' },
      { value: 'travel', text: 'Traveling somewhere new' },
    ],
  },
  {
    id: 'car_relationship',
    type: 'single' as const,
    prompt: 'Your relationship with a car?',
    options: [
      { value: 'no_car', text: "I'd rather not own one" },
      { value: 'mixed', text: 'Fine driving, but want good alternatives' },
      { value: 'car_dependent', text: "I drive everywhere — transit doesn't matter" },
    ],
  },
  {
    id: 'horizon',
    type: 'single' as const,
    prompt: 'How are you thinking about this move?',
    options: [
      { value: 'short_term', text: 'Next few years — things may change again' },
      { value: 'long_term', text: 'Long term — I want to put down real roots' },
      { value: 'forever', text: 'Retirement or forever home' },
    ],
  },
  {
    id: 'natural_scenery',
    type: 'multi' as const,
    prompt: 'What kind of natural scenery matters most to you?',
    hint: 'Pick up to 2. "No strong preference" cannot be combined with others.',
    options: [
      { value: 'mountains', text: 'Mountains or dramatic terrain' },
      { value: 'ocean', text: 'Ocean or coastline' },
      { value: 'lakes_rivers', text: 'Lakes or rivers' },
      { value: 'canopy', text: 'Tree canopy and greenery' },
      { value: 'no_preference', text: 'No strong preference' },
    ],
  },
] as const

type QuizAnswers = {
  life_stage: string | null
  weekend_energy: string | null
  car_relationship: string | null
  horizon: string | null
  natural_scenery: string[]
}

function getInitialAnswers(): QuizAnswers {
  return {
    life_stage: null,
    weekend_energy: null,
    car_relationship: null,
    horizon: null,
    natural_scenery: [],
  }
}

type PillarWeights = Record<PillarKey, number>

function inferWeights(answers: QuizAnswers): PillarWeights {
  const w: PillarWeights = {
    natural_beauty: 50,
    built_beauty: 50,
    access_to_nature: 50,
    neighborhood_amenities: 50,
    active_outdoors: 50,
    healthcare_access: 50,
    public_transit_access: 50,
    air_travel_access: 50,
    economic_security: 30,
    quality_education: 50,
    housing_value: 50,
    climate_risk: 50,
    social_fabric: 50,
  }

  const get = (k: PillarKey) => w[k]
  const set = (k: PillarKey, v: number) => { w[k] = Math.max(0, Math.min(100, v)) }

  // life_stage
  const ls = answers.life_stage
  if (ls === 'family_young') {
    set('quality_education', 90)
    set('social_fabric', 80)
    set('neighborhood_amenities', 70)
  } else if (ls === 'family_older') {
    set('quality_education', 85)
    set('social_fabric', 75)
  } else if (ls === 'empty_nester') {
    set('healthcare_access', 80)
    set('climate_risk', 70)
    set('quality_education', 20)
  } else if (ls === 'single_couple') {
    set('neighborhood_amenities', 75)
    set('air_travel_access', 65)
    set('quality_education', 20)
  }
  // flexible: no change

  // weekend_energy
  const we = answers.weekend_energy
  if (we === 'outdoors') {
    set('active_outdoors', 85)
    set('natural_beauty', 80)
  } else if (we === 'neighborhood') {
    set('neighborhood_amenities', 85)
    set('built_beauty', 70)
  } else if (we === 'home_social') {
    set('social_fabric', 80)
  } else if (we === 'travel') {
    set('air_travel_access', 85)
    set('neighborhood_amenities', 60)
  }

  // car_relationship
  const cr = answers.car_relationship
  if (cr === 'no_car') {
    set('public_transit_access', 90)
    set('neighborhood_amenities', Math.max(get('neighborhood_amenities'), 75))
  } else if (cr === 'mixed') {
    set('public_transit_access', 60)
  } else if (cr === 'car_dependent') {
    set('public_transit_access', 15)
  }

  // horizon
  const h = answers.horizon
  if (h === 'long_term') {
    set('climate_risk', Math.max(get('climate_risk'), 70))
    set('social_fabric', Math.max(get('social_fabric'), 70))
  } else if (h === 'forever') {
    set('climate_risk', Math.max(get('climate_risk'), 70))
    set('social_fabric', Math.max(get('social_fabric'), 70))
    set('healthcare_access', Math.max(get('healthcare_access'), 75))
    set('housing_value', Math.max(get('housing_value'), 65))
  } else if (h === 'short_term') {
    set('housing_value', Math.max(get('housing_value'), 70))
    set('climate_risk', Math.min(get('climate_risk'), 40))
  }

  return w
}

function weightsToPriorities(weights: PillarWeights): PillarPriorities {
  const p: PillarPriorities = {} as PillarPriorities
  for (const k of PILLAR_ORDER) {
    const v = weights[k]
    if (v >= 80) p[k] = 'High'
    else if (v >= 55) p[k] = 'Medium'
    else if (v > 0) p[k] = 'Low'
    else p[k] = 'None'
  }
  return p
}

function weightToBand(weight: number): PriorityLevel {
  if (weight >= 80) return 'High'
  if (weight >= 55) return 'Medium'
  return 'Low'
}

interface PlaceValuesGameProps {
  onApplyPriorities?: (priorities: PillarPriorities, naturalBeautyPreference?: string[]) => void
  onBack?: () => void
}

function priorityBadgeStyle(level: PriorityLevel): React.CSSProperties {
  if (level === 'High') return { background: 'var(--hf-primary-gradient)', color: '#fff' }
  if (level === 'Medium') return { background: 'rgba(102,126,234,0.14)', color: 'var(--hf-text-primary)' }
  if (level === 'Low') return { background: 'rgba(108,117,125,0.12)', color: 'var(--hf-text-primary)' }
  return { background: '#f1f3f5', color: 'var(--hf-text-secondary)' }
}

const LONGEVITY_NOTE =
  'Longevity score is calculated separately — it measures how well a place supports a long, healthy life based on Blue Zone research, independent of your priorities.'

export default function PlaceValuesGame({ onApplyPriorities, onBack }: PlaceValuesGameProps) {
  const [game_state, set_game_state] = useState<'playing' | 'results'>('playing')
  const [current_step, set_current_step] = useState(0)
  const [answers, set_answers] = useState<QuizAnswers>(getInitialAnswers)

  const start_game = useCallback(() => {
    set_game_state('playing')
    set_current_step(0)
    set_answers(getInitialAnswers())
  }, [])

  const question = QUESTIONS[current_step]

  const can_advance = useMemo(() => {
    if (!question) return false
    if (question.type === 'single') {
      const key = question.id as keyof QuizAnswers
      return answers[key] !== null && answers[key] !== undefined
    }
    if (question.type === 'multi') {
      return true // natural_scenery: 0 = no preference, 1 or 2 = valid
    }
    return false
  }, [question, answers])

  const set_single = useCallback((key: keyof QuizAnswers, value: string) => {
    set_answers((prev) => ({ ...prev, [key]: value }))
  }, [])

  const toggle_natural_scenery = useCallback((value: string) => {
    set_answers((prev) => {
      const current = prev.natural_scenery
      const is_no_pref = value === 'no_preference'
      const has_no_pref = current.includes('no_preference')

      if (is_no_pref) {
        return { ...prev, natural_scenery: current.includes('no_preference') ? [] : ['no_preference'] }
      }
      if (has_no_pref) {
        const next = current.filter((x) => x !== 'no_preference')
        const withValue = next.includes(value) ? next.filter((x) => x !== value) : [...next, value].slice(0, 2)
        return { ...prev, natural_scenery: withValue }
      }
      const next = current.includes(value)
        ? current.filter((x) => x !== value)
        : current.length >= 2
          ? [...current.slice(1), value]
          : [...current, value]
      return { ...prev, natural_scenery: next }
    })
  }, [])

  const go_prev = useCallback(() => {
    if (current_step > 0) {
      set_current_step((s) => s - 1)
      return
    }
    onBack?.()
  }, [current_step, onBack])

  const go_next = useCallback(() => {
    if (!can_advance) return
    if (current_step < TOTAL_QUESTIONS - 1) {
      set_current_step((s) => s + 1)
      return
    }
    set_game_state('results')
  }, [can_advance, current_step])

  const handle_back = useCallback(() => {
    if (game_state === 'playing') {
      go_prev()
      return
    }
    if (game_state === 'results') {
      start_game()
      return
    }
  }, [game_state, go_prev, start_game])

  const weights = useMemo(() => inferWeights(answers), [answers])
  const priorities = useMemo(() => weightsToPriorities(weights), [weights])
  const ranked_pillars = useMemo(
    () =>
      [...PILLAR_ORDER]
        .map((pillar) => ({ pillar, weight: weights[pillar] }))
        .sort((a, b) => b.weight - a.weight),
    [weights]
  )

  // Auto-apply quiz results when user reaches the results screen (once per results view).
  const appliedRef = useRef(false)
  const naturalBeautyPreference = useMemo(() => {
    const sel = answers.natural_scenery.filter((v) => v !== 'no_preference')
    if (sel.length === 0) return undefined
    return sel.length <= 2 ? sel : sel.slice(0, 2)
  }, [answers.natural_scenery])
  useEffect(() => {
    if (game_state !== 'results') {
      appliedRef.current = false
      return
    }
    if (!appliedRef.current && onApplyPriorities) {
      onApplyPriorities(priorities, naturalBeautyPreference)
      appliedRef.current = true
    }
  }, [game_state, priorities, naturalBeautyPreference, onApplyPriorities])

  // --- Playing (one question at a time)
  if (game_state === 'playing' && question) {
    const progress_pct = ((current_step + 1) / TOTAL_QUESTIONS) * 100
    const single_value = question.type === 'single' ? (answers[question.id as keyof QuizAnswers] as string | null) : null
    const multi_selected =
      question.type === 'multi'
        ? answers.natural_scenery
        : []

    return (
      <main className="hf-page">
        <AppHeader />
        <div className="hf-container">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1.5rem' }}>
            <button onClick={handle_back} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <ChevronLeft size={18} />
              Back
            </button>
            <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Question {current_step + 1} of {TOTAL_QUESTIONS}
            </div>
            <div className="hf-muted" style={{ fontWeight: 800 }}>
              {Math.round(progress_pct)}%
            </div>
          </div>
          <div className="hf-panel" style={{ marginBottom: '1.5rem' }}>
            <div style={{ height: 10, background: '#f1f3f5', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${progress_pct}%`, background: 'var(--hf-primary-gradient)', transition: 'all 0.3s ease' }} />
            </div>
          </div>
          <div className="hf-card">
            <div style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--hf-text-primary)' }}>
              {question.prompt}
            </div>
            {'hint' in question && question.hint && (
              <div className="hf-muted" style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
                {question.hint}
              </div>
            )}
            <div className="hf-grid-2">
              {question.options.map((opt) => {
                const is_selected =
                  question.type === 'single'
                    ? single_value === opt.value
                    : multi_selected.includes(opt.value)
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() =>
                      question.type === 'single'
                        ? set_single(question.id as keyof QuizAnswers, opt.value)
                        : toggle_natural_scenery(opt.value)
                    }
                    className="hf-card-sm"
                    style={{
                      textAlign: 'left',
                      borderColor: is_selected ? 'var(--hf-primary-1)' : undefined,
                      borderWidth: 2,
                      transform: is_selected ? 'translateY(-3px)' : undefined,
                      boxShadow: is_selected ? '0 8px 25px rgba(0, 0, 0, 0.12)' : undefined,
                    }}
                  >
                    <div style={{ display: 'flex', gap: '0.9rem', alignItems: 'flex-start' }}>
                      {question.type === 'multi' && (
                        <div
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 8,
                            border: `2px solid ${is_selected ? 'var(--hf-primary-1)' : '#dee2e6'}`,
                            background: is_selected ? 'var(--hf-primary-1)' : 'transparent',
                            flex: '0 0 auto',
                            marginTop: 2,
                          }}
                        />
                      )}
                      <div style={{ color: 'var(--hf-text-primary)', fontWeight: 600 }}>{opt.text}</div>
                    </div>
                  </button>
                )
              })}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginTop: '2rem' }}>
              <button type="button" onClick={go_prev} className="hf-btn-primary" disabled={current_step === 0}>
                Previous
              </button>
              <button type="button" onClick={go_next} className="hf-btn-primary" disabled={!can_advance}>
                {current_step === TOTAL_QUESTIONS - 1 ? 'See my weights →' : 'Next'}
              </button>
            </div>
          </div>
        </div>
      </main>
    )
  }

  // --- Results
  return (
    <main className="hf-page">
      <AppHeader />
      <div className="hf-container">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1.5rem' }}>
          <button onClick={handle_back} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <ChevronLeft size={18} />
            Back
          </button>
          <span />
        </div>
        <div className="hf-card">
          <h2 className="hf-section-title" style={{ marginBottom: '0.75rem' }}>
            Your priority weights
          </h2>
          <p className="hf-muted" style={{ marginBottom: '1.5rem' }}>
            All {PILLAR_ORDER.length} pillars ranked by importance. Use these to personalize your HomeFit score.
          </p>

          <div className="hf-panel" style={{ background: 'rgba(102,126,234,0.06)', border: '1px solid rgba(102,126,234,0.18)', marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
            <p className="hf-muted" style={{ margin: 0, fontSize: '0.95rem' }}>
              {LONGEVITY_NOTE}
            </p>
          </div>

          <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '1rem' }}>
            Ranked by weight
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
            {ranked_pillars.map(({ pillar, weight }) => {
              const meta = PILLAR_META[pillar]
              const band = weightToBand(weight)
              return (
                <div key={pillar} className="hf-panel" style={{ padding: '1rem 1.25rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '0.75rem' }}>
                    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                      <span style={{ fontSize: '1.5rem' }}>{meta.icon}</span>
                      <span style={{ fontWeight: 800, color: 'var(--hf-text-primary)' }}>{meta.name}</span>
                    </div>
                    <span
                      style={{
                        ...priorityBadgeStyle(band),
                        padding: '0.35rem 0.6rem',
                        borderRadius: 999,
                        fontWeight: 800,
                        fontSize: '0.85rem',
                      }}
                    >
                      {band}
                    </span>
                  </div>
                  <div style={{ height: 10, background: '#f1f3f5', borderRadius: 999, overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${weight}%`,
                        background: 'var(--hf-primary-gradient)',
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.85rem', marginTop: '0.35rem' }}>
                    {weight}
                  </div>
                </div>
              )
            })}
          </div>

          {onBack && (
            <button
              onClick={onBack}
              className="hf-btn-primary"
              style={{ width: '100%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '1rem' }}
            >
              <Search size={18} /> Search a place →
            </button>
          )}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <button onClick={start_game} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <RefreshCcw size={16} /> ← Retake
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}
