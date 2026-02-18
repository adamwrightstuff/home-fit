'use client'

import { useEffect, useRef, useState } from 'react'
import { streamScore, getScore } from '@/lib/api'
import { ScoreResponse } from '@/types/api'
import CurrentlyAnalyzing from './CurrentlyAnalyzing'
import CompletedPillars from './CompletedPillars'
import ProgressBar from './ProgressBar'
import InteractiveMap from './InteractiveMap'
import LoadingQuotes from './LoadingQuotes'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

interface SmartLoadingScreenProps {
  location: string
  on_complete: (response: ScoreResponse) => void
  on_error?: (error: Error) => void
  priorities?: string
  tokens?: string
  job_categories?: string
  include_chains?: boolean
  enable_schools?: boolean
}

const PILLAR_ORDER: PillarKey[] = [
  'natural_beauty',
  'built_beauty',
  'neighborhood_amenities',
  'active_outdoors',
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'economic_security',
  'quality_education',
  'housing_value',
]

const PILLAR_CONFIG: Record<PillarKey, { emoji: string; name: string; description: string }> = PILLAR_ORDER.reduce(
  (acc, key) => {
    acc[key] = { emoji: PILLAR_META[key].icon, name: PILLAR_META[key].name, description: PILLAR_META[key].description }
    return acc
  },
  {} as Record<PillarKey, { emoji: string; name: string; description: string }>
)

export default function SmartLoadingScreen({ 
  location, 
  on_complete, 
  on_error,
  priorities,
  tokens,
  job_categories,
  include_chains,
  enable_schools
}: SmartLoadingScreenProps) {
  const [current_pillar, set_current_pillar] = useState<string | null>(null)
  const [completed_pillars, set_completed_pillars] = useState<Map<string, { score: number; details?: any }>>(new Map())
  const [expected_pillars, set_expected_pillars] = useState<PillarKey[]>(PILLAR_ORDER)
  const [progress, set_progress] = useState(0)
  const [coordinates, set_coordinates] = useState<{ lat: number; lon: number } | null>(null)
  const [status, set_status] = useState<'starting' | 'analyzing' | 'complete'>('starting')
  const [final_score, set_final_score] = useState<number | null>(null)
  const progress_ref = useRef(0)

  useEffect(() => {
    progress_ref.current = progress
  }, [progress])

  useEffect(() => {
    let cancelled = false
    let soft_progress_interval: ReturnType<typeof setInterval> | null = null
    const timeouts: Array<ReturnType<typeof setTimeout>> = []

    const clear_soft_progress = () => {
      if (soft_progress_interval) {
        clearInterval(soft_progress_interval)
        soft_progress_interval = null
      }
    }

    const clear_all_timeouts = () => {
      for (const t of timeouts) clearTimeout(t)
      timeouts.length = 0
    }

    set_current_pillar(null)
    set_completed_pillars(new Map())
    set_expected_pillars(PILLAR_ORDER)
    set_progress(0)
    set_coordinates(null)
    set_status('starting')
    set_final_score(null)

    const SOFT_FLOOR = 6
    const SOFT_CAP = 32
    const SOFT_EASE_MS = 9000

    const stopStream = streamScore(
      { location, tokens, priorities, job_categories, include_chains, enable_schools },
      (ev) => {
        if (cancelled) return
        if (ev.status === 'started') {
          set_status('analyzing')
          set_progress((p) => Math.max(p, SOFT_FLOOR))
          clear_soft_progress()
          const soft_start = Date.now()
          soft_progress_interval = setInterval(() => {
            if (cancelled) return
            const elapsed = Date.now() - soft_start
            const eased = SOFT_CAP - (SOFT_CAP - SOFT_FLOOR) * Math.exp(-elapsed / SOFT_EASE_MS)
            set_progress((p) => Math.max(p, Math.min(SOFT_CAP, eased)))
          }, 250)
        }
        if (ev.status === 'analyzing' && ev.coordinates) {
          set_coordinates(ev.coordinates)
        }
        if (ev.status === 'complete' && ev.pillar != null && ev.completed != null && ev.total != null) {
          clear_soft_progress()
          const base = Math.min(SOFT_CAP, Math.max(SOFT_FLOOR, progress_ref.current || 0))
          const frac = ev.completed / Math.max(1, ev.total)
          set_progress(base + frac * (100 - base))
          set_completed_pillars((prev) => {
            const next = new Map(prev)
            next.set(ev.pillar!, { score: ev.score ?? 0 })
            return next
          })
        }
        if (ev.status === 'done' && ev.response) {
          clear_soft_progress()
          const resp = ev.response
          const respPillars = (resp.livability_pillars as any) || {}
          const pillarOrder = PILLAR_ORDER.filter((k) => Boolean(respPillars?.[k]))
          const effectiveOrder = pillarOrder.length ? pillarOrder : PILLAR_ORDER
          set_expected_pillars(effectiveOrder)
          const completed = new Map<string, { score: number; details?: any }>()
          for (const k of effectiveOrder) {
            const pd = respPillars[k]
            if (pd != null) completed.set(k, { score: Number(pd?.score ?? 0), details: pd })
          }
          set_completed_pillars(completed)
          set_status('complete')
          set_progress(100)
          set_final_score(typeof resp.total_score === 'number' ? resp.total_score : null)
          if (resp.coordinates) set_coordinates(resp.coordinates)
          const t = setTimeout(() => {
            if (!cancelled) on_complete(resp)
          }, 500)
          timeouts.push(t)
        }
        if (ev.status === 'error') {
          clear_soft_progress()
          set_status('complete')
          set_progress(0)
          set_final_score(null)
          if (on_error) on_error(new Error(ev.message ?? ev.error ?? 'Stream error'))
        }
      },
      (err) => {
        if (cancelled) return
        clear_soft_progress()
        const streamUnavailable = /404|Not Found|stream failed/i.test(String(err?.message ?? ''))
        if (streamUnavailable) {
          getScore({ location, tokens, priorities, job_categories, include_chains, enable_schools })
            .then((r) => {
              if (cancelled) return
              set_completed_pillars((prev) => {
                const pillars = (r.livability_pillars || {}) as Record<string, { score?: number }>
                const next = new Map<string, { score: number; details?: any }>()
                for (const k of PILLAR_ORDER) {
                  const pd = pillars[k]
                  if (pd != null) next.set(k, { score: Number(pd?.score ?? 0), details: pd })
                }
                return next
              })
              set_status('complete')
              set_progress(100)
              set_final_score(typeof r.total_score === 'number' ? r.total_score : null)
              if (r.coordinates) set_coordinates(r.coordinates)
              const t = setTimeout(() => { if (!cancelled) on_complete(r) }, 500)
              timeouts.push(t)
            })
            .catch((e) => {
              if (cancelled) return
              set_status('complete')
              set_progress(0)
              set_final_score(null)
              if (on_error) on_error(e)
            })
        } else {
          set_status('complete')
          set_progress(0)
          set_final_score(null)
          if (on_error) on_error(err)
        }
      }
    )

    return () => {
      cancelled = true
      stopStream()
      clear_soft_progress()
      clear_all_timeouts()
    }
  }, [location, priorities, tokens, job_categories, include_chains, enable_schools, on_complete, on_error])

  // Update current pillar based on which ones are not yet completed
  useEffect(() => {
    if (status === 'analyzing') {
      // Before we have any pillar results, we can't truthfully claim a specific pillar
      // is being computed (backend work is opaque and often parallel). Show a neutral
      // "preparing data" phase instead.
      if (completed_pillars.size === 0) {
        set_current_pillar(null)
        return
      }
      const remaining = expected_pillars.filter((p) => !completed_pillars.has(p))
      
      if (remaining.length > 0) {
        set_current_pillar(String(remaining[0]))
      } else {
        set_current_pillar(null)
      }
    } else {
      set_current_pillar(null)
    }
  }, [completed_pillars, expected_pillars, status])

  return (
    <div className="hf-page hf-viewport hf-safe-bottom overflow-y-auto md:overflow-hidden" style={{ width: '100%', position: 'relative' }}>
      {/* Main content - always render so map can initialize */}
      <div className="flex flex-col md:flex-row h-full w-full">
        {/* Left side - Map */}
        <div 
          className="w-full md:w-1/2 h-[42svh] min-h-[260px] md:h-full"
          style={{ 
            position: 'relative',
            overflow: 'hidden'
          }}
        >
          <InteractiveMap 
            location={location}
            coordinates={coordinates}
            completed_pillars={Array.from(completed_pillars.keys())}
          />
        </div>

        {/* Right side - Progress */}
        <div
          className="w-full md:w-1/2 p-4 md:p-8 overflow-visible md:overflow-y-auto"
          style={{ position: 'relative', WebkitOverflowScrolling: 'touch' }}
        >
          {/* Loading overlay - only on right side */}
          {status === 'starting' && (
            <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: 'var(--hf-bg-gradient)' }}>
              <div className="text-center max-w-md px-4">
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--hf-text-primary)', marginBottom: '0.5rem' }}>
                  Initializing…
                </div>
                <div className="hf-muted" style={{ marginBottom: '1.5rem' }}>
                  Preparing to analyze {location}
                </div>
                <LoadingQuotes is_loading={true} />
              </div>
            </div>
          )}
          
          <div className="max-w-2xl mx-auto">
            <div className="hf-section-title" style={{ marginBottom: '0.75rem' }}>
              Analyzing {location}
            </div>
            
            <ProgressBar progress={progress} />
            
            <div className="mb-6">
              <LoadingQuotes is_loading={status !== 'complete'} />
            </div>
            
            {final_score !== null && (
              <div className="hf-panel" style={{ marginBottom: '1.5rem' }}>
                <div className="hf-score-hero" style={{ padding: '1rem 1.25rem', borderRadius: 16 }}>
                  <div className="hf-score-hero__value" style={{ fontSize: '2.5rem' }}>
                    {final_score.toFixed(1)}
                  </div>
                  <div className="hf-score-hero__label">Final score</div>
                </div>
              </div>
            )}
            
            {status === 'analyzing' && completed_pillars.size === 0 && (
              <div className="hf-panel" style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={{ fontSize: '2rem' }}>🧭</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)', marginBottom: '0.25rem' }}>
                      Preparing data…
                    </div>
                    <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
                      Geocoding your location and fetching shared datasets used across multiple pillars.
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.35rem' }} aria-hidden="true">
                    <div style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--hf-primary-1)', opacity: 0.7 }} />
                    <div style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--hf-primary-1)', opacity: 0.45 }} />
                    <div style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--hf-primary-1)', opacity: 0.25 }} />
                  </div>
                </div>
              </div>
            )}

            {current_pillar && status === 'analyzing' && completed_pillars.size > 0 && (
              <CurrentlyAnalyzing
                pillar_key={current_pillar}
                config={(PILLAR_CONFIG as any)[current_pillar]}
              />
            )}
            
            <CompletedPillars 
              completed_pillars={completed_pillars}
              pillar_config={PILLAR_CONFIG}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
