'use client'

import { useEffect, useState } from 'react'
import { getScore } from '@/lib/api'
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
  include_chains,
  enable_schools
}: SmartLoadingScreenProps) {
  const [current_pillar, set_current_pillar] = useState<string | null>(null)
  const [completed_pillars, set_completed_pillars] = useState<Map<string, { score: number; details?: any }>>(new Map())
  const [progress, set_progress] = useState(0)
  const [coordinates, set_coordinates] = useState<{ lat: number; lon: number } | null>(null)
  const [status, set_status] = useState<'starting' | 'analyzing' | 'complete'>('starting')
  const [final_score, set_final_score] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false

    // Reset UI state for new request
    set_current_pillar(null)
    set_completed_pillars(new Map())
    set_progress(0)
    set_coordinates(null)
    set_status('starting')
    set_final_score(null)

    const run = async () => {
      try {
        // Brief "initializing" phase for UX parity with prior streaming UI
        await new Promise((r) => setTimeout(r, 300))
        if (cancelled) return
        set_status('analyzing')

        const response = await getScore({
          location,
          priorities,
          include_chains,
          enable_schools,
        })

        if (cancelled) return
        if (!response || typeof response.total_score !== 'number') {
          throw new Error('Scoring response was incomplete. Please refresh and try again.')
        }
        if (response.coordinates) {
          set_coordinates(response.coordinates)
        }

        // Animate pillar completion in a deterministic order to keep the UX engaging.
        const pillarOrder = PILLAR_ORDER
        pillarOrder.forEach((pillarKey, idx) => {
          const delayMs = 220 * idx
          setTimeout(() => {
            if (cancelled) return
            const pillarData = (response.livability_pillars as any)?.[pillarKey]
            const score = Number(pillarData?.score ?? 0)
            set_completed_pillars((prev) => {
              const next = new Map(prev)
              next.set(pillarKey, { score, details: pillarData })
              set_progress((next.size / 9) * 100)
              return next
            })
          }, delayMs)
        })

        const totalAnimationMs = 220 * pillarOrder.length
        setTimeout(() => {
          if (cancelled) return
          set_status('complete')
          set_progress(100)
          set_final_score(typeof response.total_score === 'number' ? response.total_score : null)
          setTimeout(() => {
            if (!cancelled) on_complete(response)
          }, 500)
        }, totalAnimationMs)
      } catch (e) {
        if (cancelled) return
        const err = e instanceof Error ? e : new Error('Unknown error')
        set_status('complete')
        set_progress(0)
        set_final_score(null)
        if (on_error) on_error(err)
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [location, priorities, include_chains, enable_schools, on_complete, on_error])

  // Update current pillar based on which ones are not yet completed
  useEffect(() => {
    if (status === 'analyzing') {
      const all_pillars = Object.keys(PILLAR_CONFIG)
      const remaining = all_pillars.filter(p => !completed_pillars.has(p))
      
      if (remaining.length > 0) {
        set_current_pillar(remaining[0])
      } else {
        set_current_pillar(null)
      }
    } else {
      set_current_pillar(null)
    }
  }, [completed_pillars, status])

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
            
            {current_pillar && status === 'analyzing' && (
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
