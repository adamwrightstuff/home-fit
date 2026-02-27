'use client'

import React, { useMemo, useState } from 'react'
import { ArrowLeft, Check, ChevronLeft, ChevronRight, MapPin, RefreshCcw } from 'lucide-react'
import type { PillarPriorities, PriorityLevel } from './SearchOptions'
import AppHeader from './AppHeader'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

// Maximum possible points per pillar (audited across all 20 questions)
const max_possible_scores: Record<keyof PillarPriorities, number> = {
  active_outdoors: 43,
  built_beauty: 41,
  natural_beauty: 39,
  neighborhood_amenities: 60,
  layout_network: 0,
  air_travel_access: 22,
  public_transit_access: 20,
  healthcare_access: 23,
  economic_security: 2,
  quality_education: 32,
  housing_value: 45,
  climate_risk: 50,
  social_fabric: 40,
}

const PILLAR_ORDER: Array<keyof PillarPriorities> = [
  'natural_beauty',
  'built_beauty',
  'neighborhood_amenities',
  'layout_network',
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

const questions = [
  {
    id: 1,
    text: "It's Saturday morning. What sounds most appealing?",
    options: [
      { text: 'Hiking a mountain trail with epic views', pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: 'Wandering through a historic district with unique architecture', pillars: { built_beauty: 4 } },
      { text: 'Browsing the farmers market and grabbing brunch at a local café', pillars: { neighborhood_amenities: 4 } },
      { text: 'Staying in and enjoying a spacious, comfortable home', pillars: { housing_value: 4 } },
    ],
  },
  {
    id: 2,
    text: 'Your ideal evening walk takes you past...',
    options: [
      { text: 'Tree-lined streets with mature canopy and gardens', pillars: { natural_beauty: 4 } },
      { text: 'Charming rowhouses with character and front porches', pillars: { built_beauty: 4 } },
      { text: 'Bustling sidewalks with shops, restaurants, and street performers', pillars: { neighborhood_amenities: 4 } },
      { text: 'A waterfront path with sunset views', pillars: { active_outdoors: 2, natural_beauty: 2 } },
    ],
  },
  {
    id: 3,
    text: "You're considering two neighborhoods. What's most reassuring?",
    options: [
      { text: 'Top-rated hospital within 10 minutes', pillars: { healthcare_access: 5 } },
      { text: 'Highly-rated schools and educational programs', pillars: { quality_education: 5 } },
      { text: 'Beautiful tree-covered streets and nearby parks', pillars: { natural_beauty: 3, active_outdoors: 2 } },
      { text: 'More space and lower cost per square foot', pillars: { housing_value: 5 } },
    ],
  },
  {
    id: 4,
    text: "You're offered two jobs with identical pay. One major difference:",
    options: [
      { text: 'Job A: 15-min subway ride downtown', pillars: { public_transit_access: 4, economic_security: 1 } },
      { text: 'Job B: 30-min scenic drive through nature', pillars: { natural_beauty: 2, active_outdoors: 2 } },
      { text: 'Job C: 5-min walk from your front door', pillars: { neighborhood_amenities: 4, economic_security: 2 } },
      { text: 'Job D: Remote, but near a major airport for frequent travel', pillars: { air_travel_access: 4 } },
    ],
  },
  {
    id: 5,
    text: 'If you had kids (or have kids now), what matters most about where you live?',
    options: [
      { text: 'Top-rated schools with excellent academics', pillars: { quality_education: 5 } },
      { text: "Safe streets where they can walk to friends' houses", pillars: { neighborhood_amenities: 5 } },
      { text: 'Nearby parks, trails, and outdoor play spaces', pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: 'A bigger, more affordable home with space to grow', pillars: { housing_value: 5 } },
    ],
  },
  {
    id: 6,
    text: "What's the biggest dealbreaker for a potential home?",
    options: [
      { text: 'Poor school ratings in the district', pillars: { quality_education: 5 } },
      { text: 'Far from hospitals and urgent care', pillars: { healthcare_access: 5 } },
      { text: 'Cookie-cutter development with zero character', pillars: { built_beauty: 4, natural_beauty: 1 } },
      { text: "Nothing walkable—you'd need to drive everywhere", pillars: { neighborhood_amenities: 5 } },
    ],
  },
  {
    id: 7,
    text: "You've saved up for something special. What excites you most?",
    options: [
      { text: 'A beautifully designed home with architectural details', pillars: { built_beauty: 4 } },
      { text: 'A bigger place where everyone has their own space', pillars: { housing_value: 5 } },
      { text: 'A home in a top school district', pillars: { quality_education: 5 } },
      { text: 'A property backing onto nature trails or a park', pillars: { active_outdoors: 2, natural_beauty: 2 } },
    ],
  },
  {
    id: 8,
    text: 'How do you feel about the cost of living where you want to be?',
    options: [
      { text: 'I want maximum space and value for my budget', pillars: { housing_value: 5 } },
      { text: "I'll pay more for beautiful architecture and character", pillars: { built_beauty: 4 } },
      { text: 'Affordability matters, but so does access to good schools', pillars: { housing_value: 3, quality_education: 2 } },
      { text: "I'll prioritize location over square footage", pillars: { neighborhood_amenities: 4 } },
    ],
  },
  {
    id: 9,
    text: 'Your perfect weekend getaway is...',
    options: [
      { text: 'A 2-hour drive to a national park', pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: 'A quick flight to a new city to explore', pillars: { air_travel_access: 5 } },
      { text: 'A train ride to a charming historic town', pillars: { public_transit_access: 3, built_beauty: 1 } },
      { text: 'Actually, I love staying home—my neighborhood has everything', pillars: { neighborhood_amenities: 4 } },
    ],
  },
  {
    id: 10,
    text: "When you think about getting around and traveling, what's most important?",
    options: [
      { text: 'Being near a major international airport', pillars: { air_travel_access: 5 } },
      { text: 'Having comprehensive public transit (buses, trains, rail)', pillars: { public_transit_access: 5 } },
      { text: 'Living close enough to walk to most places', pillars: { neighborhood_amenities: 4 } },
      { text: 'Having scenic routes for driving and road trips', pillars: { natural_beauty: 3, active_outdoors: 1 } },
    ],
  },
  {
    id: 11,
    text: 'What would make you feel instantly at home in a new place?',
    options: [
      { text: 'Discovering a network of biking and hiking trails', pillars: { active_outdoors: 5 } },
      { text: 'Finding excellent doctors and healthcare nearby', pillars: { healthcare_access: 5 } },
      { text: 'A welcoming neighborhood with friendly local shops and cafes', pillars: { neighborhood_amenities: 5 } },
      { text: 'Noticing tree-lined streets and parks everywhere', pillars: { natural_beauty: 5 } },
    ],
  },
  {
    id: 12,
    text: "Imagine your daily commute. What's ideal?",
    options: [
      { text: 'A quick train or subway ride', pillars: { public_transit_access: 5 } },
      { text: 'A 10-minute walk through my neighborhood', pillars: { neighborhood_amenities: 4 } },
      { text: 'A scenic drive with nature views', pillars: { natural_beauty: 2, active_outdoors: 2 } },
      { text: 'Working from home with occasional airport trips', pillars: { air_travel_access: 3 } },
    ],
  },
  {
    id: 13,
    text: 'When you imagine your ideal view from your window...',
    options: [
      { text: 'Mountains, hills, or dramatic natural landscapes', pillars: { natural_beauty: 3, active_outdoors: 1 } },
      { text: 'A vibrant street scene with people and activity', pillars: { neighborhood_amenities: 4 } },
      { text: 'Water—ocean, lake, or river', pillars: { active_outdoors: 2, natural_beauty: 2 } },
      { text: 'Beautiful buildings and interesting architecture', pillars: { built_beauty: 4 } },
    ],
  },
  {
    id: 14,
    text: 'A family member needs regular medical appointments. What setup works best?',
    options: [
      { text: 'Multiple specialists and a major hospital nearby', pillars: { healthcare_access: 5 } },
      { text: 'A reliable clinic within walking distance', pillars: { healthcare_access: 3, neighborhood_amenities: 2 } },
      { text: 'Good transit connections to medical facilities', pillars: { healthcare_access: 3, public_transit_access: 2 } },
      { text: "Honestly, we'd drive wherever needed—proximity isn't critical", pillars: { housing_value: 3 } },
    ],
  },
  {
    id: 15,
    text: 'How do you envision spending time with your family or future family?',
    options: [
      { text: 'At great local schools and educational activities', pillars: { quality_education: 5 } },
      { text: 'Exploring hiking trails and outdoor adventures', pillars: { active_outdoors: 3, natural_beauty: 1 } },
      { text: 'In a spacious, affordable home with room to grow', pillars: { housing_value: 4 } },
      { text: 'Walking to parks, cafes, and neighborhood events', pillars: { neighborhood_amenities: 4 } },
    ],
  },
  {
    id: 16,
    text: 'What kind of recreational opportunities do you want nearby?',
    options: [
      { text: 'Serious hiking, climbing, or mountain sports', pillars: { active_outdoors: 5 } },
      { text: 'Cultural venues—theaters, museums, galleries', pillars: { neighborhood_amenities: 3, built_beauty: 2 } },
      { text: 'Casual urban parks for walking and relaxation', pillars: { active_outdoors: 2, natural_beauty: 2 } },
      { text: 'Historic sites and architecturally significant areas', pillars: { built_beauty: 4 } },
    ],
  },
  {
    id: 17,
    text: "You're house hunting. Which feature makes you say 'this is it'?",
    options: [
      { text: "It's near top-rated schools", pillars: { quality_education: 5 } },
      { text: "It's spacious and affordable with room to grow", pillars: { housing_value: 5 } },
      { text: 'It backs onto a forest, park, or greenbelt', pillars: { natural_beauty: 3, active_outdoors: 1 } },
      { text: "It's in a neighborhood with stunning homes and streetscapes", pillars: { built_beauty: 4 } },
    ],
  },
  {
    id: 18,
    text: "When considering a place's connectivity, what matters most?",
    options: [
      { text: 'Major airport within an hour—I travel frequently', pillars: { air_travel_access: 5 } },
      { text: 'Excellent public transit network throughout the region', pillars: { public_transit_access: 5 } },
      { text: 'Easy access to daily amenities—walkable or short drive works', pillars: { neighborhood_amenities: 4 } },
      { text: 'Highway access for weekend trips to nature', pillars: { active_outdoors: 2, natural_beauty: 2 } },
    ],
  },
  {
    id: 19,
    text: "What aspect of a neighborhood's character speaks to you most?",
    options: [
      { text: 'Architectural diversity and historic buildings', pillars: { built_beauty: 5 } },
      { text: 'Tree canopy and natural green spaces', pillars: { natural_beauty: 5 } },
      { text: 'Strong sense of community and local culture', pillars: { neighborhood_amenities: 4 } },
      { text: 'Access to trails and outdoor recreation', pillars: { active_outdoors: 5 } },
    ],
  },
  {
    id: 20,
    text: "What's your non-negotiable when choosing where to live?",
    options: [
      { text: 'Access to nature and outdoor activities', pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: 'Top-tier schools and educational opportunities', pillars: { quality_education: 5 } },
      { text: 'Excellent healthcare facilities and medical access', pillars: { healthcare_access: 5 } },
      { text: 'Excellent value and space for the price', pillars: { housing_value: 5 } },
    ],
  },
] as const

interface PlaceValuesGameProps {
  onApplyPriorities?: (priorities: PillarPriorities) => void
  onBack?: () => void
}

function priorityBadgeStyle(level: PriorityLevel): React.CSSProperties {
  if (level === 'High') return { background: 'var(--hf-primary-gradient)', color: '#fff' }
  if (level === 'Medium') return { background: 'rgba(102,126,234,0.14)', color: 'var(--hf-text-primary)' }
  if (level === 'Low') return { background: 'rgba(108,117,125,0.12)', color: 'var(--hf-text-primary)' }
  return { background: '#f1f3f5', color: 'var(--hf-text-secondary)' }
}

export default function PlaceValuesGame({ onApplyPriorities, onBack }: PlaceValuesGameProps) {
  const [game_state, set_game_state] = useState<'intro' | 'playing' | 'results'>('intro')
  const [current_question, set_current_question] = useState(0)
  const [answers, set_answers] = useState<Array<number | null>>(() => Array(questions.length).fill(null))

  const start_game = () => {
    set_game_state('playing')
    set_current_question(0)
    set_answers(Array(questions.length).fill(null))
  }

  const scores = useMemo(() => {
    const next: Record<keyof PillarPriorities, number> = {
      active_outdoors: 0,
      built_beauty: 0,
      natural_beauty: 0,
      neighborhood_amenities: 0,
      air_travel_access: 0,
      public_transit_access: 0,
      healthcare_access: 0,
      economic_security: 0,
      quality_education: 0,
      housing_value: 0,
      climate_risk: 0,
      social_fabric: 0,
    }

    answers.forEach((selectedIdx, qIdx) => {
      if (selectedIdx === null) return
      const option = questions[qIdx]?.options?.[selectedIdx]
      if (!option) return
      Object.entries(option.pillars).forEach(([pillar, points]) => {
        const key = pillar as keyof PillarPriorities
        next[key] = (next[key] || 0) + (points || 0)
      })
    })

    return next
  }, [answers])

  const set_answer_for_current = (option_index: number) => {
    set_answers((prev) => {
      const next = [...prev]
      next[current_question] = option_index
      return next
    })
  }

  const go_prev = () => {
    if (current_question > 0) {
      set_current_question((q) => q - 1)
      return
    }
    set_game_state('intro')
  }

  const go_next = () => {
    if (answers[current_question] === null) return
    if (current_question < questions.length - 1) {
      set_current_question((q) => q + 1)
      return
    }
    set_game_state('results')
  }

  const handle_back = () => {
    if (game_state === 'playing') {
      go_prev()
      return
    }
    if (game_state === 'results') {
      set_game_state('intro')
      return
    }
    if (game_state === 'intro' && onBack) onBack()
  }

  const convert_scores_to_priorities = (): PillarPriorities => {
    const pillar_data: Array<{ pillar: keyof PillarPriorities; score: number; percentage: number }> = []

    Object.keys(scores).forEach((pillar_key) => {
      const pillar = pillar_key as keyof PillarPriorities
      const score = scores[pillar]
      const max_possible = max_possible_scores[pillar]
      const percentage = max_possible > 0 ? (score / max_possible) * 100 : 0
      pillar_data.push({ pillar, score, percentage })
    })

    pillar_data.sort((a, b) => b.score - a.score)
    const non_zero_pillars = pillar_data.filter((p) => p.score > 0)

    if (non_zero_pillars.length === 0) {
      const all_medium: PillarPriorities = {} as PillarPriorities
      PILLAR_ORDER.forEach((key) => {
        all_medium[key] = 'Medium'
      })
      return all_medium
    }

    const priorities: PillarPriorities = {} as PillarPriorities

    non_zero_pillars.forEach((item, index) => {
      const percentile_rank = (index + 1) / non_zero_pillars.length
      let priority: PriorityLevel

      if (percentile_rank <= 0.33 && item.percentage >= 25) priority = 'High'
      else if (percentile_rank <= 0.7 || (item.percentage >= 15 && item.percentage < 25)) priority = 'Medium'
      else if (item.percentage >= 5 || item.score > 0) priority = 'Low'
      else priority = 'None'

      priorities[item.pillar] = priority
    })

    pillar_data.forEach((item) => {
      if (item.score === 0) priorities[item.pillar] = 'None'
    })

    PILLAR_ORDER.forEach((pillar_key) => {
      if (!priorities[pillar_key]) priorities[pillar_key] = 'None'
    })

    const has_high = Object.values(priorities).some((p) => p === 'High')
    if (!has_high && non_zero_pillars.length > 0) {
      priorities[non_zero_pillars[0].pillar] = 'High'
    }

    return priorities
  }

  const get_all_pillars = () => {
    const priorities = convert_scores_to_priorities()
    return PILLAR_ORDER
      .map((pillar) => ({
        pillar,
        score: scores[pillar],
        priority: priorities[pillar],
      }))
      .sort((a, b) => b.score - a.score)
  }

  const get_profile_summary = (sorted_pillars: ReturnType<typeof get_all_pillars>) => {
    const top = sorted_pillars.filter((p) => p.priority === 'High' || p.priority === 'Medium').slice(0, 3)
    if (top.length === 0) return 'Your answers suggest you’re still exploring what matters most in a location.'
    const names = top.map((p) => PILLAR_META[p.pillar as PillarKey].name)
    return `Your Place Values profile highlights what you want to optimize for in a neighborhood. Your top priorities are **${names[0]}**${names[1] ? `, **${names[1]}**` : ''}${names[2] ? `, and **${names[2]}**` : ''}.`
  }

  const handle_apply_priorities = () => {
    const priorities = convert_scores_to_priorities()
    if (onApplyPriorities) onApplyPriorities(priorities)
  }

  if (game_state === 'intro') {
    return (
      <main className="hf-page">
        <AppHeader />
        <div className="hf-container">
          <div className="hf-card" style={{ maxWidth: 900, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center' }}>
              {onBack ? (
                <button onClick={handle_back} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ArrowLeft size={18} />
                  Back
                </button>
              ) : (
                <span />
              )}
              <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Place Values Quiz
              </div>
              <span />
            </div>

            <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
              <div
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: 18,
                  margin: '0 auto 1.5rem',
                  background: 'rgba(102,126,234,0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <MapPin size={32} color="var(--hf-primary-1)" />
              </div>
              <h2 className="hf-section-title" style={{ marginBottom: '0.75rem' }}>
                Discover what matters most to you
              </h2>
              <p className="hf-muted" style={{ maxWidth: 720, margin: '0 auto 2rem' }}>
                Answer 20 quick scenarios. We’ll turn your preferences into priorities you can apply to your HomeFit score.
              </p>
              <button onClick={start_game} className="hf-btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                Start Quiz <ChevronRight size={18} />
              </button>
            </div>
          </div>
        </div>
      </main>
    )
  }

  if (game_state === 'playing') {
    const question = questions[current_question]
    const progress = ((current_question + 1) / questions.length) * 100
    const selected = answers[current_question]

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
              Question {current_question + 1} of {questions.length}
            </div>
            <div className="hf-muted" style={{ fontWeight: 800 }}>
              {Math.round(progress)}%
            </div>
          </div>

          <div className="hf-panel" style={{ marginBottom: '1.5rem' }}>
            <div style={{ height: 10, background: '#f1f3f5', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${progress}%`, background: 'var(--hf-primary-gradient)', transition: 'all 0.3s ease' }} />
            </div>
          </div>

          <div className="hf-card">
            <div style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '1.5rem', color: 'var(--hf-text-primary)' }}>
              {question.text}
            </div>

            <div className="hf-grid-2">
              {question.options.map((option, idx) => {
                const isActive = selected === idx
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => set_answer_for_current(idx)}
                    className="hf-card-sm"
                    style={{
                      textAlign: 'left',
                      borderColor: isActive ? 'var(--hf-primary-1)' : undefined,
                      transform: isActive ? 'translateY(-3px)' : undefined,
                      boxShadow: isActive ? '0 8px 25px rgba(0, 0, 0, 0.12)' : undefined,
                    }}
                  >
                    <div style={{ display: 'flex', gap: '0.9rem', alignItems: 'flex-start' }}>
                      <div
                        style={{
                          width: 34,
                          height: 34,
                          borderRadius: 10,
                          background: isActive ? 'var(--hf-primary-gradient)' : '#f1f3f5',
                          color: isActive ? '#ffffff' : 'var(--hf-text-secondary)',
                          fontWeight: 800,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flex: '0 0 auto',
                        }}
                      >
                        {idx + 1}
                      </div>
                      <div style={{ color: 'var(--hf-text-primary)', fontWeight: 600 }}>{option.text}</div>
                    </div>
                  </button>
                )
              })}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginTop: '2rem' }}>
              <button type="button" onClick={go_prev} className="hf-btn-primary" disabled={current_question === 0}>
                Previous
              </button>
              <button type="button" onClick={go_next} className="hf-btn-primary" disabled={answers[current_question] === null}>
                {current_question === questions.length - 1 ? 'View Results' : 'Next'}
              </button>
            </div>
          </div>
        </div>
      </main>
    )
  }

  const all_pillars = get_all_pillars()

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
            Your Place Values Profile
          </h2>

          <div className="hf-panel" style={{ background: 'rgba(102,126,234,0.08)', border: '1px solid rgba(102,126,234,0.18)', marginBottom: '2rem' }}>
            <div
              className="hf-muted"
              style={{ margin: 0, fontSize: '1.05rem' }}
              dangerouslySetInnerHTML={{
                __html: get_profile_summary(all_pillars).replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--hf-primary-2)">$1</strong>'),
              }}
            />
            <div className="hf-muted" style={{ marginTop: '0.75rem', fontSize: '0.95rem' }}>
              We translate this profile into priority weights (None/Low/Medium/High) that personalize your HomeFit score.
            </div>
          </div>

          <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '1rem' }}>
            Results by pillar
          </div>

          <div className="hf-grid-3" style={{ marginBottom: '2rem' }}>
            {all_pillars.map(({ pillar, score, priority }) => {
              const meta = PILLAR_META[pillar as PillarKey]
              const max = max_possible_scores[pillar]
              const pct = max > 0 ? Math.min(100, Math.max(0, (score / max) * 100)) : 0

              return (
                <div key={pillar} className="hf-panel">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                      <div style={{ fontSize: '1.5rem' }}>{meta.icon}</div>
                      <div>
                        <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)' }}>{meta.name}</div>
                        <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
                          {meta.description}
                        </div>
                      </div>
                    </div>
                    <span
                      style={{
                        ...priorityBadgeStyle(priority),
                        padding: '0.35rem 0.6rem',
                        borderRadius: 999,
                        fontWeight: 800,
                        fontSize: '0.85rem',
                      }}
                    >
                      {priority}
                    </span>
                  </div>

                  <div style={{ marginTop: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
                      <span className="hf-muted" style={{ fontSize: '0.9rem' }}>
                        Strength
                      </span>
                      <span className="hf-muted" style={{ fontSize: '0.9rem', fontWeight: 700 }}>
                        {pct.toFixed(0)}%
                      </span>
                    </div>
                    <div style={{ height: 10, background: '#f1f3f5', borderRadius: 999, overflow: 'hidden', marginTop: '0.5rem' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: 'var(--hf-primary-gradient)', transition: 'all 0.3s ease' }} />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {onApplyPriorities ? (
            <button
              onClick={handle_apply_priorities}
              className="hf-btn-primary"
              style={{ width: '100%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
            >
              <Check size={18} /> View Your Personalized Score
            </button>
          ) : null}

          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '1.5rem' }}>
            <button onClick={start_game} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <RefreshCcw size={16} /> Reset quiz
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}

