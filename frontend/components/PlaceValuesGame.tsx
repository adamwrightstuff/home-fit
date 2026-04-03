'use client'

import React, { useMemo, useState, useCallback, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ChevronLeft, Loader2, RefreshCcw, Search } from 'lucide-react'
import type { PillarPriorities, PriorityLevel } from './SearchOptions'
import { JOB_CATEGORY_OPTIONS } from './SearchOptions'
import AppHeader from './AppHeader'
import { PILLAR_META, PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import {
  fetchAgentRecommendations,
  hydrateRecommendationResultsNavigation,
  quizAnswersToAgentContext,
  type AgentRecommendResponse,
} from '@/lib/agentRecommend'

const TOTAL_QUESTIONS = 7

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
    id: 'community_vibe',
    type: 'single' as const,
    prompt: 'What community character matters most to you?',
    options: [
      { value: 'diverse', text: 'A diverse mix of cultures, ages, and backgrounds' },
      { value: 'architectural', text: 'Architecturally rich, with character and history' },
      { value: 'tight_knit', text: 'Tight-knit — neighbors know each other' },
      { value: 'eclectic', text: 'Lively and eclectic — always something happening' },
      { value: 'quiet_settled', text: 'Quiet, settled, and consistent' },
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
      { value: 'canopy', text: 'Greenery' },
      { value: 'no_preference', text: 'No strong preference' },
    ],
  },
  {
    id: 'work',
    type: 'multi' as const,
    prompt: 'Which job sectors matter to you — or are you mainly remote?',
    hint: 'Optional. Select any that apply to personalize Economic Opportunity.',
    options: JOB_CATEGORY_OPTIONS.map((o) => ({ value: o.key, text: o.label, description: o.description })),
  },
] as const

type QuizAnswers = {
  life_stage: string | null
  weekend_energy: string | null
  car_relationship: string | null
  horizon: string | null
  natural_scenery: string[]
  job_categories: string[]
  community_vibe: string | null
}

function getInitialAnswers(): QuizAnswers {
  return {
    life_stage: null,
    weekend_energy: null,
    car_relationship: null,
    horizon: null,
    natural_scenery: [],
    job_categories: [],
    community_vibe: null,
  }
}

type PillarWeights = Record<PillarKey, number>

function inferWeights(answers: QuizAnswers): PillarWeights {
  const w: PillarWeights = {
    natural_beauty: 50,
    built_beauty: 50,
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
    diversity: 50,
  }

  const get = (k: PillarKey) => w[k]
  const set = (k: PillarKey, v: number) => { w[k] = Math.max(0, Math.min(100, v)) }

  // life_stage
  const ls = answers.life_stage
  if (ls === 'family_young') {
    set('quality_education', 90)
    set('social_fabric', 80)
    set('neighborhood_amenities', 70)
    set('housing_value', Math.max(get('housing_value'), 65))
    set('healthcare_access', Math.max(get('healthcare_access'), 60))
  } else if (ls === 'family_older') {
    set('quality_education', 85)
    set('social_fabric', 75)
    set('housing_value', Math.max(get('housing_value'), 65))
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
    set('housing_value', Math.max(get('housing_value'), 65))
  } else if (h === 'forever') {
    set('climate_risk', Math.max(get('climate_risk'), 70))
    set('social_fabric', Math.max(get('social_fabric'), 70))
    set('healthcare_access', Math.max(get('healthcare_access'), 75))
    set('housing_value', Math.max(get('housing_value'), 65))
  } else if (h === 'short_term') {
    set('housing_value', Math.max(get('housing_value'), 70))
    set('climate_risk', Math.min(get('climate_risk'), 40))
  }

  // community_vibe → diversity (primary) + built_beauty + social_fabric
  const cv = answers.community_vibe
  if (cv === 'diverse') {
    set('diversity', 85)
    set('social_fabric', Math.max(get('social_fabric'), 70))
  } else if (cv === 'architectural') {
    set('built_beauty', 85)
    set('neighborhood_amenities', Math.max(get('neighborhood_amenities'), 65))
    set('diversity', 40)
  } else if (cv === 'tight_knit') {
    set('social_fabric', Math.max(get('social_fabric'), 85))
    set('diversity', 30)
  } else if (cv === 'eclectic') {
    set('neighborhood_amenities', Math.max(get('neighborhood_amenities'), 80))
    set('diversity', 65)
  } else if (cv === 'quiet_settled') {
    set('social_fabric', Math.max(get('social_fabric'), 60))
    set('diversity', 25)
  }

  // natural_scenery: if user picked 1–2 scenery types (not "no strong preference"), boost Natural Beauty importance
  const scenery = answers.natural_scenery.filter((v) => v !== 'no_preference')
  if (scenery.length > 0) {
    set('natural_beauty', Math.max(get('natural_beauty'), 80))
  }

  // job_categories:
  // - If user selected any local sector(s), increase Economic Opportunity importance
  // - If they ONLY selected Remote / Flexible, local economy should matter less
  if (answers.job_categories.length > 0) {
    const jobs = answers.job_categories
    const hasRemote = jobs.includes('remote_flexible')
    const hasNonRemote = jobs.some((k) => k !== 'remote_flexible')

    if (hasNonRemote) {
      // At least one concrete local sector: boost Economic Opportunity
      set('economic_security', Math.max(get('economic_security'), 65))
    } else if (hasRemote) {
      // Remote only: local job market matters less than default
      set('economic_security', Math.min(get('economic_security'), 20))
    }
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

interface PlaceValuesGameProps {
  onApplyPriorities?: (priorities: PillarPriorities, naturalBeautyPreference?: string[], job_categories?: string[]) => void
  onBack?: () => void
}

/** Matches backend prerank weights — bar width for each chosen level. */
const PRIORITY_BAR_PCT: Record<PriorityLevel, number> = {
  None: 0,
  Low: 33,
  Medium: 66,
  High: 100,
}

const PRIORITY_LEVELS: PriorityLevel[] = ['None', 'Low', 'Medium', 'High']

function priorityBadgeStyle(level: PriorityLevel): React.CSSProperties {
  if (level === 'High') return { background: 'var(--hf-primary-gradient)', color: '#fff' }
  if (level === 'Medium') return { background: 'rgba(102,126,234,0.14)', color: 'var(--hf-text-primary)' }
  if (level === 'Low') return { background: 'rgba(108,117,125,0.12)', color: 'var(--hf-text-primary)' }
  return { background: '#f1f3f5', color: 'var(--hf-text-secondary)' }
}

export default function PlaceValuesGame({ onApplyPriorities, onBack }: PlaceValuesGameProps) {
  const router = useRouter()
  const [game_state, set_game_state] = useState<'playing' | 'results' | 'recommendations'>('playing')
  const [current_step, set_current_step] = useState(0)
  const [answers, set_answers] = useState<QuizAnswers>(getInitialAnswers)
  const [agent_loading, set_agent_loading] = useState(false)
  const [agent_error, set_agent_error] = useState<string | null>(null)
  const [agent_response, set_agent_response] = useState<AgentRecommendResponse | null>(null)
  const [edited_priorities, set_edited_priorities] = useState<PillarPriorities | null>(null)
  const recommendationsHeadingRef = useRef<HTMLHeadingElement>(null)

  const start_game = useCallback(() => {
    set_game_state('playing')
    set_current_step(0)
    set_answers(getInitialAnswers())
    set_agent_loading(false)
    set_agent_error(null)
    set_agent_response(null)
    set_edited_priorities(null)
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

  const toggle_job_categories = useCallback((value: string) => {
    set_answers((prev) => {
      const current = prev.job_categories
      const next = current.includes(value) ? current.filter((x) => x !== value) : [...current, value]
      return { ...prev, job_categories: next }
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
    if (game_state === 'recommendations') {
      set_game_state('results')
      set_agent_error(null)
      return
    }
    if (game_state === 'results') {
      start_game()
      return
    }
  }, [game_state, go_prev, start_game])

  const weights = useMemo(() => inferWeights(answers), [answers])
  const priorities = useMemo(() => weightsToPriorities(weights), [weights])
  const effective_priorities = edited_priorities ?? priorities

  const ranked_priority_rows = useMemo(
    () =>
      [...PILLAR_ORDER]
        .map((pillar) => {
          const level = effective_priorities[pillar]
          return {
            pillar,
            level,
            bar_pct: PRIORITY_BAR_PCT[level],
          }
        })
        .sort((a, b) => b.bar_pct - a.bar_pct || a.pillar.localeCompare(b.pillar)),
    [effective_priorities]
  )

  useEffect(() => {
    if (game_state === 'playing') {
      set_edited_priorities(null)
    }
  }, [game_state])

  useEffect(() => {
    if (game_state === 'results') {
      set_edited_priorities((prev) => (prev !== null ? prev : { ...priorities }))
    }
  }, [game_state, priorities])

  const set_pillar_priority = useCallback(
    (pillar: PillarKey, level: PriorityLevel) => {
      set_edited_priorities((prev) => {
        const base: PillarPriorities = { ...(prev ?? priorities) }
        return { ...base, [pillar]: level }
      })
    },
    [priorities]
  )

  const load_recommendations = useCallback(async () => {
    set_agent_error(null)
    set_agent_loading(true)
    set_agent_response(null)
    try {
      const ctx = quizAnswersToAgentContext(answers)
      const p = edited_priorities ?? priorities
      const data = await fetchAgentRecommendations(p, ctx)
      set_agent_response(data)
      set_game_state('recommendations')
    } catch (e) {
      set_agent_error(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      set_agent_loading(false)
    }
  }, [answers, edited_priorities, priorities])

  const naturalBeautyPreference = useMemo(() => {
    const sel = answers.natural_scenery.filter((v) => v !== 'no_preference')
    if (sel.length === 0) return undefined
    return sel.length <= 2 ? sel : sel.slice(0, 2)
  }, [answers.natural_scenery])

  useEffect(() => {
    if (game_state !== 'results') return
    onApplyPriorities?.(effective_priorities, naturalBeautyPreference, answers.job_categories)
  }, [game_state, effective_priorities, naturalBeautyPreference, answers.job_categories, onApplyPriorities])

  useEffect(() => {
    if (game_state === 'recommendations' && agent_response) {
      queueMicrotask(() => recommendationsHeadingRef.current?.focus())
    }
  }, [game_state, agent_response])

  // --- Recommendations (agent API)
  if (game_state === 'recommendations' && agent_response) {
    const recs = agent_response.recommendations
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
          <section className="hf-card" aria-labelledby="agent-rec-heading">
            <h2
              ref={recommendationsHeadingRef}
              id="agent-rec-heading"
              tabIndex={-1}
              className="hf-section-title"
              style={{ marginBottom: '0.5rem', outline: 'none' }}
            >
              Top picks for you
            </h2>
            <p className="hf-muted" style={{ marginBottom: '0.35rem' }}>
              From our pre-scored NYC metro catalog — same pillars you just set.
            </p>
            <p className="hf-muted" style={{ marginBottom: '1.25rem', fontSize: '0.9rem' }}>
              &quot;Status signature&quot; labels describe neighborhood character (not statistical percentiles).
            </p>
            {typeof agent_response.meta?.processing_ms === 'number' && (
              <p className="hf-muted" style={{ marginBottom: '1rem', fontSize: '0.85rem' }}>
                Ready in {agent_response.meta.processing_ms} ms
              </p>
            )}
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {recs.length === 0 && (
              <p className="hf-muted" role="status">
                No recommendations returned. Try again in a moment.
              </p>
            )}
            {recs.map((rec) => (
                <li key={rec.neighborhood} className="hf-panel" style={{ padding: '1.15rem 1.25rem' }}>
                  <div style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--hf-text-primary)', marginBottom: '0.35rem' }}>
                    {rec.neighborhood}
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.9rem', marginBottom: '0.75rem' }}>
                    {rec.archetype}
                    {rec.percentile_band ? ` · ${rec.percentile_band}` : ''}
                  </div>
                  <div
                    style={{ marginBottom: '0.75rem' }}
                    aria-label={`Match score ${rec.match_score} out of 100`}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                      <span className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        Match
                      </span>
                      <span style={{ fontWeight: 800 }}>{rec.match_score}</span>
                    </div>
                    <div style={{ height: 8, background: '#f1f3f5', borderRadius: 999, overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${Math.min(100, Math.max(0, rec.match_score))}%`,
                          background: 'var(--hf-primary-gradient)',
                        }}
                      />
                    </div>
                  </div>
                  {rec.top_drivers?.length > 0 && (
                    <div style={{ marginBottom: '0.65rem', fontSize: '0.9rem' }}>
                      <span className="hf-muted">Top drivers: </span>
                      {rec.top_drivers.map((k) => PILLAR_META[k as PillarKey]?.name ?? k).join(' · ')}
                    </div>
                  )}
                  <p style={{ margin: '0 0 1rem', color: 'var(--hf-text-secondary)', lineHeight: 1.5 }}>{rec.explanation}</p>
                  <Link
                    href={rec.results_url}
                    className="hf-btn-primary"
                    onClick={(e) => {
                      e.preventDefault()
                      hydrateRecommendationResultsNavigation(rec)
                      router.push(rec.results_url)
                    }}
                    style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '100%', textDecoration: 'none' }}
                  >
                    View full score
                  </Link>
                </li>
              ))}
            </ul>
            {onBack && (
              <button
                type="button"
                onClick={onBack}
                className="hf-btn-primary"
                style={{
                  width: '100%',
                  marginTop: '1.25rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  background: 'transparent',
                  color: 'var(--hf-primary-1)',
                  border: '2px solid var(--hf-primary-1)',
                  boxShadow: 'none',
                }}
              >
                <Search size={18} /> Search a place
              </button>
            )}
          </section>
        </div>
      </main>
    )
  }

  // --- Playing (one question at a time)
  if (game_state === 'playing' && question) {
    const progress_pct = ((current_step + 1) / TOTAL_QUESTIONS) * 100
    const single_value = question.type === 'single' ? (answers[question.id as keyof QuizAnswers] as string | null) : null
    const multi_selected =
      question.type === 'multi'
        ? question.id === 'natural_scenery'
          ? answers.natural_scenery
          : question.id === 'work'
            ? answers.job_categories
            : []
        : []
    const handle_multi_toggle = question.id === 'natural_scenery' ? toggle_natural_scenery : question.id === 'work' ? toggle_job_categories : (() => {})

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
                        : handle_multi_toggle(opt.value)
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
                      <div style={{ color: 'var(--hf-text-primary)', fontWeight: 600 }}>
                        {opt.text}
                        {'description' in opt && opt.description && (
                          <div className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.25rem', fontWeight: 400 }}>
                            {opt.description}
                          </div>
                        )}
                      </div>
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

  // --- Results (weights)
  if (game_state === 'results') {
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
            Ranked by importance (highest first). Bars show strength for your current level (None / Low / Medium / High). Change any pillar with the dropdown, then get neighborhood picks or search a place.
          </p>

          <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '1rem' }}>
            Ranked by importance
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
            {ranked_priority_rows.map(({ pillar, level, bar_pct }) => {
              const meta = PILLAR_META[pillar]
              return (
                <div key={pillar} className="hf-panel" style={{ padding: '1rem 1.25rem' }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '0.75rem',
                      marginBottom: '0.75rem',
                      flexWrap: 'wrap',
                    }}
                  >
                    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', minWidth: 0 }}>
                      <span style={{ fontSize: '1.5rem' }} aria-hidden>
                        {meta.icon}
                      </span>
                      <span style={{ fontWeight: 800, color: 'var(--hf-text-primary)' }}>{meta.name}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <span
                        style={{
                          ...priorityBadgeStyle(level),
                          padding: '0.35rem 0.6rem',
                          borderRadius: 999,
                          fontWeight: 800,
                          fontSize: '0.85rem',
                        }}
                      >
                        {level}
                      </span>
                      <select
                        value={level}
                        onChange={(e) => set_pillar_priority(pillar, e.target.value as PriorityLevel)}
                        aria-label={`${meta.name} priority`}
                        style={{
                          padding: '0.45rem 0.75rem',
                          borderRadius: 8,
                          border: '1px solid rgba(0,0,0,0.12)',
                          fontWeight: 700,
                          background: 'var(--hf-card-bg, #fff)',
                          color: 'var(--hf-text-primary)',
                          minWidth: '120px',
                        }}
                      >
                        {PRIORITY_LEVELS.map((lv) => (
                          <option key={lv} value={lv}>
                            {lv}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div style={{ height: 10, background: '#f1f3f5', borderRadius: 999, overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${bar_pct}%`,
                        background: 'var(--hf-primary-gradient)',
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.85rem', marginTop: '0.35rem' }}>
                    Strength {bar_pct}
                  </div>
                </div>
              )
            })}
          </div>

          {agent_error && (
            <div
              className="hf-panel"
              role="alert"
              style={{
                marginBottom: '1rem',
                padding: '0.85rem 1rem',
                border: '1px solid rgba(220, 53, 69, 0.35)',
                background: 'rgba(220, 53, 69, 0.06)',
              }}
            >
              <p style={{ margin: '0 0 0.5rem', color: 'var(--hf-text-primary)' }}>{agent_error}</p>
              <button type="button" className="hf-btn-link" onClick={load_recommendations} style={{ fontWeight: 700 }}>
                Retry
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={load_recommendations}
            disabled={agent_loading}
            className="hf-btn-primary"
            style={{ width: '100%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '1rem' }}
          >
            {agent_loading ? (
              <>
                <Loader2 size={18} className="animate-spin" aria-hidden />
                Finding neighborhoods…
              </>
            ) : (
              <>See neighborhood picks for you</>
            )}
          </button>

          {onBack && (
            <button
              type="button"
              onClick={onBack}
              disabled={agent_loading}
              className="hf-btn-primary"
              style={{
                width: '100%',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                marginBottom: '1rem',
                background: 'transparent',
                color: 'var(--hf-primary-1)',
                border: '2px solid var(--hf-primary-1)',
                boxShadow: 'none',
              }}
            >
              <Search size={18} /> Search a place →
            </button>
          )}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <button type="button" onClick={start_game} disabled={agent_loading} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <RefreshCcw size={16} /> ← Retake
            </button>
          </div>
        </div>
      </div>
    </main>
    )
  }

  return null
}
