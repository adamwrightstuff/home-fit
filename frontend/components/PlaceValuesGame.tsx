'use client'

import React, { useMemo, useState } from 'react'
import { ArrowLeft, Check, ChevronLeft, ChevronRight, MapPin, RefreshCcw } from 'lucide-react'
import type { PillarPriorities, PriorityLevel } from './SearchOptions'
import AppHeader from './AppHeader'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

const PILLAR_ORDER: Array<keyof PillarPriorities> = [
  'natural_beauty',
  'built_beauty',
  'neighborhood_amenities',
  'active_outdoors',
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'quality_education',
  'housing_value',
]

type PillarPoints = Partial<Record<keyof PillarPriorities, number>>

type QuizOption = {
  text: string
  pillars: PillarPoints
}

type QuizQuestion =
  | {
      id: number
      type: 'single'
      text: string
      helper?: string
      options: QuizOption[]
    }
  | {
      id: number
      type: 'multi'
      text: string
      helper?: string
      minSelect: number
      maxSelect: number
      options: QuizOption[]
    }
  | {
      id: number
      type: 'rank'
      text: string
      helper?: string
      rankCount: number
      rankLabels?: string[]
      rankWeights: number[]
      options: QuizOption[]
    }

const questions: QuizQuestion[] = [
  {
    id: 1,
    type: 'rank',
    text: 'How do you prefer to spend a Saturday?',
    helper: 'Rank your top 3.',
    rankCount: 3,
    rankLabels: ['#1', '#2', '#3'],
    rankWeights: [4, 3, 2],
    options: [
      { text: 'Exploring hiking trails and outdoor recreation', pillars: { active_outdoors: 1, natural_beauty: 1 } },
      { text: 'Walking through neighborhoods with historic architecture', pillars: { built_beauty: 1 } },
      { text: 'Browsing farmers markets and trying local cafés', pillars: { neighborhood_amenities: 1 } },
      { text: 'Enjoying time at home with plenty of space', pillars: { housing_value: 1 } },
    ],
  },
  {
    id: 2,
    type: 'rank',
    text: 'What makes an evening walk appealing?',
    helper: 'Rank your top 2.',
    rankCount: 2,
    rankLabels: ['#1', '#2'],
    rankWeights: [4, 3],
    options: [
      { text: 'Tree-lined streets with gardens and green spaces', pillars: { natural_beauty: 1 } },
      { text: 'Charming streetscapes with architectural character', pillars: { built_beauty: 1 } },
      { text: 'Lively streets with shops, restaurants, and street life', pillars: { neighborhood_amenities: 1 } },
      { text: 'Scenic waterfront paths', pillars: { active_outdoors: 1, natural_beauty: 1 } },
    ],
  },
  {
    id: 3,
    type: 'multi',
    text: 'What gives you peace of mind about a place?',
    helper: 'Select 2–4.',
    minSelect: 2,
    maxSelect: 4,
    options: [
      { text: 'A top-rated hospital nearby', pillars: { healthcare_access: 4 } },
      { text: 'Highly-rated schools in the district', pillars: { quality_education: 4 } },
      { text: 'Tree-covered streets and accessible parks', pillars: { natural_beauty: 3, active_outdoors: 1 } },
      { text: 'Getting good value and space for your money', pillars: { housing_value: 4 } },
    ],
  },
  {
    id: 4,
    type: 'rank',
    text: "What's your ideal commute situation?",
    helper: 'Rank preferences 1–4.',
    rankCount: 4,
    rankLabels: ['#1', '#2', '#3', '#4'],
    rankWeights: [4, 3, 2, 1],
    options: [
      { text: 'Reliable subway or train service', pillars: { public_transit_access: 1 } },
      { text: 'A scenic drive with good roads', pillars: { active_outdoors: 1, natural_beauty: 1 } },
      { text: 'Walking or biking to work and daily needs', pillars: { neighborhood_amenities: 1 } },
      { text: 'Easy access to a major airport', pillars: { air_travel_access: 1 } },
    ],
  },
  {
    id: 5,
    type: 'rank',
    text: 'If you have (or plan to have) kids, what matters most?',
    helper: 'Rank top to bottom.',
    rankCount: 4,
    rankLabels: ['Top', '2nd', '3rd', 'Bottom'],
    rankWeights: [4, 3, 2, 1],
    options: [
      { text: 'Top-rated schools', pillars: { quality_education: 1 } },
      { text: 'Safe, walkable streets', pillars: { neighborhood_amenities: 1 } },
      { text: 'Nearby parks and outdoor activities', pillars: { active_outdoors: 1, natural_beauty: 1 } },
      { text: 'Enough space for the family to grow', pillars: { housing_value: 1 } },
    ],
  },
  {
    id: 6,
    type: 'multi',
    text: 'What would be a dealbreaker for you?',
    helper: 'Select all that apply.',
    minSelect: 1,
    maxSelect: 4,
    options: [
      { text: 'Poor school ratings', pillars: { quality_education: 4 } },
      { text: 'Limited access to quality healthcare', pillars: { healthcare_access: 4 } },
      { text: 'Generic, characterless development', pillars: { built_beauty: 4 } },
      { text: 'Having to drive everywhere for basics', pillars: { public_transit_access: 2, neighborhood_amenities: 2 } },
    ],
  },
  {
    id: 7,
    type: 'rank',
    text: 'If you could splurge on one aspect of where you live, what would it be?',
    helper: 'Rank 1–4.',
    rankCount: 4,
    rankLabels: ['#1', '#2', '#3', '#4'],
    rankWeights: [4, 3, 2, 1],
    options: [
      { text: 'A home with architectural character and thoughtful design', pillars: { built_beauty: 1 } },
      { text: 'More square footage and living space', pillars: { housing_value: 1 } },
      { text: 'Being in the best school district', pillars: { quality_education: 1 } },
      { text: 'A property backing onto nature', pillars: { active_outdoors: 1, natural_beauty: 1 } },
    ],
  },
  {
    id: 8,
    type: 'rank',
    text: 'How do you think about cost of living?',
    helper: 'Rank your top 2.',
    rankCount: 2,
    rankLabels: ['#1', '#2'],
    rankWeights: [4, 3],
    options: [
      { text: 'I want maximum space and value for my money', pillars: { housing_value: 1 } },
      { text: "I'm willing to pay more for beautiful surroundings", pillars: { built_beauty: 1, natural_beauty: 1 } },
      { text: 'Good schools justify higher costs', pillars: { quality_education: 1 } },
      { text: 'I prioritize location and convenience over size', pillars: { neighborhood_amenities: 1, public_transit_access: 1 } },
    ],
  },
  {
    id: 9,
    type: 'rank',
    text: 'What kind of connectivity matters to you?',
    helper: 'Choose your top 2.',
    rankCount: 2,
    rankLabels: ['#1', '#2'],
    rankWeights: [4, 3],
    options: [
      { text: 'Being near a major airport', pillars: { air_travel_access: 1 } },
      { text: 'Having comprehensive public transit options', pillars: { public_transit_access: 1 } },
      { text: 'Walking to daily amenities and services', pillars: { neighborhood_amenities: 1 } },
      { text: 'Easy access to scenic roads and highways', pillars: { active_outdoors: 1, natural_beauty: 1 } },
    ],
  },
  {
    id: 10,
    type: 'single',
    text: 'If you had to choose just one non-negotiable, what would it be?',
    helper: 'Select one.',
    options: [
      { text: 'Access to nature and outdoor recreation', pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: 'Top-rated schools', pillars: { quality_education: 5 } },
      { text: 'Quality healthcare nearby', pillars: { healthcare_access: 5 } },
      { text: 'Getting the best value and space for your family budget', pillars: { housing_value: 5 } },
    ],
  },
]

type QuizAnswer =
  | { kind: 'single'; selected: number | null }
  | { kind: 'multi'; selected: boolean[] }
  | { kind: 'rank'; ranked: number[] }

function empty_answers(): QuizAnswer[] {
  return questions.map((q) => {
    if (q.type === 'single') return { kind: 'single', selected: null }
    if (q.type === 'multi') return { kind: 'multi', selected: Array(q.options.length).fill(false) }
    return { kind: 'rank', ranked: [] }
  })
}

function compute_scores_from_answers(answers: QuizAnswer[]): Record<keyof PillarPriorities, number> {
  const next: Record<keyof PillarPriorities, number> = {
    active_outdoors: 0,
    built_beauty: 0,
    natural_beauty: 0,
    neighborhood_amenities: 0,
    air_travel_access: 0,
    public_transit_access: 0,
    healthcare_access: 0,
    quality_education: 0,
    housing_value: 0,
  }

  answers.forEach((answer, qIdx) => {
    const q = questions[qIdx]
    if (!q) return

    if (q.type === 'single' && answer.kind === 'single') {
      if (answer.selected === null) return
      const option = q.options[answer.selected]
      if (!option) return
      Object.entries(option.pillars).forEach(([pillar, points]) => {
        const key = pillar as keyof PillarPriorities
        next[key] = (next[key] || 0) + (points || 0)
      })
      return
    }

    if (q.type === 'multi' && answer.kind === 'multi') {
      answer.selected.forEach((isOn, optionIdx) => {
        if (!isOn) return
        const option = q.options[optionIdx]
        if (!option) return
        Object.entries(option.pillars).forEach(([pillar, points]) => {
          const key = pillar as keyof PillarPriorities
          next[key] = (next[key] || 0) + (points || 0)
        })
      })
      return
    }

    if (q.type === 'rank' && answer.kind === 'rank') {
      answer.ranked.forEach((optionIdx, rankIdx) => {
        const option = q.options[optionIdx]
        const weight = q.rankWeights[rankIdx] ?? 0
        if (!option || weight <= 0) return
        Object.entries(option.pillars).forEach(([pillar, basePoints]) => {
          const key = pillar as keyof PillarPriorities
          next[key] = (next[key] || 0) + (basePoints || 0) * weight
        })
      })
      return
    }
  })

  return next
}

function compute_max_possible_scores(): Record<keyof PillarPriorities, number> {
  const max: Record<keyof PillarPriorities, number> = {
    active_outdoors: 0,
    built_beauty: 0,
    natural_beauty: 0,
    neighborhood_amenities: 0,
    air_travel_access: 0,
    public_transit_access: 0,
    healthcare_access: 0,
    quality_education: 0,
    housing_value: 0,
  }

  const pillarKeys = Object.keys(max) as Array<keyof PillarPriorities>

  const addQuestionMax = (pillar: keyof PillarPriorities, value: number) => {
    max[pillar] = (max[pillar] || 0) + value
  }

  questions.forEach((q) => {
    pillarKeys.forEach((pillar) => {
      let bestForPillar = 0

      if (q.type === 'single') {
        q.options.forEach((opt) => {
          bestForPillar = Math.max(bestForPillar, opt.pillars[pillar] || 0)
        })
        addQuestionMax(pillar, bestForPillar)
        return
      }

      if (q.type === 'multi') {
        const n = q.options.length
        const minSel = q.minSelect
        const maxSel = q.maxSelect
        for (let mask = 0; mask < 1 << n; mask++) {
          let count = 0
          let sum = 0
          for (let i = 0; i < n; i++) {
            if ((mask & (1 << i)) === 0) continue
            count++
            sum += q.options[i]?.pillars?.[pillar] || 0
          }
          if (count < minSel || count > maxSel) continue
          bestForPillar = Math.max(bestForPillar, sum)
        }
        addQuestionMax(pillar, bestForPillar)
        return
      }

      // rank
      const n = q.options.length
      const r = q.rankCount
      const used = Array(n).fill(false)
      const chosen: number[] = []

      const dfs = () => {
        if (chosen.length === r) {
          let sum = 0
          for (let pos = 0; pos < r; pos++) {
            const optIdx = chosen[pos]
            const w = q.rankWeights[pos] ?? 0
            sum += (q.options[optIdx]?.pillars?.[pillar] || 0) * w
          }
          bestForPillar = Math.max(bestForPillar, sum)
          return
        }
        for (let i = 0; i < n; i++) {
          if (used[i]) continue
          used[i] = true
          chosen.push(i)
          dfs()
          chosen.pop()
          used[i] = false
        }
      }

      dfs()
      addQuestionMax(pillar, bestForPillar)
    })
  })

  return max
}

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
  const [answers, set_answers] = useState<QuizAnswer[]>(() => empty_answers())

  const max_possible_scores = useMemo(() => compute_max_possible_scores(), [])

  const start_game = () => {
    set_game_state('playing')
    set_current_question(0)
    set_answers(empty_answers())
  }

  const scores = useMemo(() => {
    return compute_scores_from_answers(answers)
  }, [answers])

  const set_single_for_current = (option_index: number) => {
    set_answers((prev) => {
      const next = [...prev]
      const current = next[current_question]
      if (!current || current.kind !== 'single') return prev
      next[current_question] = { kind: 'single', selected: option_index }
      return next
    })
  }

  const toggle_multi_for_current = (option_index: number) => {
    set_answers((prev) => {
      const next = [...prev]
      const q = questions[current_question]
      const current = next[current_question]
      if (!q || q.type !== 'multi' || !current || current.kind !== 'multi') return prev
      const selected = [...current.selected]
      const isOn = !!selected[option_index]
      const countOn = selected.filter(Boolean).length
      if (!isOn && countOn >= q.maxSelect) return prev
      selected[option_index] = !isOn
      next[current_question] = { kind: 'multi', selected }
      return next
    })
  }

  const rank_pick_for_current = (option_index: number) => {
    set_answers((prev) => {
      const next = [...prev]
      const q = questions[current_question]
      const current = next[current_question]
      if (!q || q.type !== 'rank' || !current || current.kind !== 'rank') return prev
      const ranked = [...current.ranked]
      const existingIdx = ranked.indexOf(option_index)
      if (existingIdx >= 0) {
        ranked.splice(existingIdx, 1)
      } else {
        if (ranked.length >= q.rankCount) return prev
        ranked.push(option_index)
      }
      next[current_question] = { kind: 'rank', ranked }
      return next
    })
  }

  const clear_rank_for_current = () => {
    set_answers((prev) => {
      const next = [...prev]
      const current = next[current_question]
      if (!current || current.kind !== 'rank') return prev
      next[current_question] = { kind: 'rank', ranked: [] }
      return next
    })
  }

  const move_rank_item_for_current = (rank_index: number, delta: -1 | 1) => {
    set_answers((prev) => {
      const next = [...prev]
      const q = questions[current_question]
      const current = next[current_question]
      if (!q || q.type !== 'rank' || !current || current.kind !== 'rank') return prev
      const ranked = [...current.ranked]
      const toIndex = rank_index + delta
      if (rank_index < 0 || rank_index >= ranked.length) return prev
      if (toIndex < 0 || toIndex >= ranked.length) return prev
      const tmp = ranked[rank_index]
      ranked[rank_index] = ranked[toIndex]
      ranked[toIndex] = tmp
      next[current_question] = { kind: 'rank', ranked }
      return next
    })
  }

  const remove_rank_item_for_current = (rank_index: number) => {
    set_answers((prev) => {
      const next = [...prev]
      const q = questions[current_question]
      const current = next[current_question]
      if (!q || q.type !== 'rank' || !current || current.kind !== 'rank') return prev
      const ranked = [...current.ranked]
      if (rank_index < 0 || rank_index >= ranked.length) return prev
      ranked.splice(rank_index, 1)
      next[current_question] = { kind: 'rank', ranked }
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
    const q = questions[current_question]
    const a = answers[current_question]
    if (!q || !a) return
    if (q.type === 'single' && (a.kind !== 'single' || a.selected === null)) return
    if (q.type === 'multi' && a.kind === 'multi') {
      const count = a.selected.filter(Boolean).length
      if (count < q.minSelect || count > q.maxSelect) return
    }
    if (q.type === 'rank' && (a.kind !== 'rank' || a.ranked.length !== q.rankCount)) return
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
                Answer 10 quick scenarios. We’ll turn your preferences into priorities you can apply to your HomeFit score.
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
    const currentAnswer = answers[current_question]

    const canProceed = (() => {
      if (!question || !currentAnswer) return false
      if (question.type === 'single' && currentAnswer.kind === 'single') return currentAnswer.selected !== null
      if (question.type === 'multi' && currentAnswer.kind === 'multi') {
        const count = currentAnswer.selected.filter(Boolean).length
        return count >= question.minSelect && count <= question.maxSelect
      }
      if (question.type === 'rank' && currentAnswer.kind === 'rank') return currentAnswer.ranked.length === question.rankCount
      return false
    })()

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
                const baseStyle: React.CSSProperties = { textAlign: 'left' }

                if (question.type === 'single' && currentAnswer?.kind === 'single') {
                  const isActive = currentAnswer.selected === idx
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => set_single_for_current(idx)}
                      className="hf-card-sm"
                      style={{
                        ...baseStyle,
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
                }

                if (question.type === 'multi' && currentAnswer?.kind === 'multi') {
                  const isActive = !!currentAnswer.selected[idx]
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => toggle_multi_for_current(idx)}
                      className="hf-card-sm"
                      style={{
                        ...baseStyle,
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
                          {isActive ? '✓' : idx + 1}
                        </div>
                        <div style={{ color: 'var(--hf-text-primary)', fontWeight: 600 }}>{option.text}</div>
                      </div>
                    </button>
                  )
                }

                if (question.type === 'rank' && currentAnswer?.kind === 'rank') {
                  const rankIdx = currentAnswer.ranked.indexOf(idx)
                  const isActive = rankIdx >= 0
                  const label = question.rankLabels?.[rankIdx] || (rankIdx >= 0 ? `#${rankIdx + 1}` : `${idx + 1}`)
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => rank_pick_for_current(idx)}
                      className="hf-card-sm"
                      style={{
                        ...baseStyle,
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
                          {isActive ? label : idx + 1}
                        </div>
                        <div style={{ color: 'var(--hf-text-primary)', fontWeight: 600 }}>{option.text}</div>
                      </div>
                    </button>
                  )
                }

                return null
              })}
            </div>

            {question.helper ? (
              <div className="hf-muted" style={{ marginTop: '1rem' }}>
                {question.helper}
                {question.type === 'multi' && currentAnswer?.kind === 'multi'
                  ? ` (${currentAnswer.selected.filter(Boolean).length}/${question.maxSelect})`
                  : null}
                {question.type === 'rank' && currentAnswer?.kind === 'rank' ? ` (${currentAnswer.ranked.length}/${question.rankCount})` : null}
              </div>
            ) : null}

            {question.type === 'rank' && currentAnswer?.kind === 'rank' ? (
              <div className="hf-panel" style={{ marginTop: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
                  <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Your ranking
                  </div>
                  <button type="button" onClick={clear_rank_for_current} className="hf-btn-link">
                    Clear
                  </button>
                </div>

                {currentAnswer.ranked.length === 0 ? (
                  <div className="hf-muted" style={{ marginTop: '0.5rem' }}>
                    Tap options above to add them in order. You can reorder below.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: '0.75rem', marginTop: '0.75rem' }}>
                    {currentAnswer.ranked.map((optionIdx, rankIdx) => {
                      const label = question.rankLabels?.[rankIdx] || `#${rankIdx + 1}`
                      const optText = question.options[optionIdx]?.text || 'Option'
                      return (
                        <div
                          key={`${optionIdx}-${rankIdx}`}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '1rem',
                            padding: '0.75rem 0.9rem',
                            border: '1px solid var(--hf-border)',
                            borderRadius: 14,
                            background: '#fff',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <div
                              style={{
                                width: 34,
                                height: 34,
                                borderRadius: 10,
                                background: 'var(--hf-primary-gradient)',
                                color: '#fff',
                                fontWeight: 900,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flex: '0 0 auto',
                              }}
                            >
                              {label}
                            </div>
                            <div style={{ color: 'var(--hf-text-primary)', fontWeight: 650 }}>{optText}</div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <button
                              type="button"
                              className="hf-btn-link"
                              onClick={() => move_rank_item_for_current(rankIdx, -1)}
                              disabled={rankIdx === 0}
                            >
                              Up
                            </button>
                            <button
                              type="button"
                              className="hf-btn-link"
                              onClick={() => move_rank_item_for_current(rankIdx, 1)}
                              disabled={rankIdx === currentAnswer.ranked.length - 1}
                            >
                              Down
                            </button>
                            <button type="button" className="hf-btn-link" onClick={() => remove_rank_item_for_current(rankIdx)}>
                              Remove
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            ) : null}

            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginTop: '2rem' }}>
              <button type="button" onClick={go_prev} className="hf-btn-primary" disabled={current_question === 0}>
                Previous
              </button>
              <button type="button" onClick={go_next} className="hf-btn-primary" disabled={!canProceed}>
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

