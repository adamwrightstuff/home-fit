'use client'

import { useEffect, useState } from 'react'
import { getScore } from '@/lib/api'
import { ScoreResponse } from '@/types/api'
import CurrentlyAnalyzing from './CurrentlyAnalyzing'
import CompletedPillars from './CompletedPillars'
import ProgressBar from './ProgressBar'
import InteractiveMap from './InteractiveMap'
import LoadingQuotes from './LoadingQuotes'

interface SmartLoadingScreenProps {
  location: string
  on_complete: (response: ScoreResponse) => void
  on_error?: (error: Error) => void
  priorities?: string
  include_chains?: boolean
  enable_schools?: boolean
}

const PILLAR_CONFIG: Record<string, { emoji: string; name: string; description: string }> = {
  active_outdoors: { emoji: '🏃', name: 'Active Outdoors', description: 'Parks, trails, and recreation' },
  built_beauty: { emoji: '🏛️', name: 'Built Beauty', description: 'Architecture and streetscapes' },
  natural_beauty: { emoji: '🌳', name: 'Natural Beauty', description: 'Tree canopy and natural features' },
  neighborhood_amenities: { emoji: '🏪', name: 'Neighborhood Amenities', description: 'Coffee, groceries, restaurants' },
  air_travel_access: { emoji: '✈️', name: 'Air Travel Access', description: 'Airport distance and options' },
  public_transit_access: { emoji: '🚇', name: 'Public Transit', description: 'Subway, bus, rail coverage' },
  healthcare_access: { emoji: '🏥', name: 'Healthcare Access', description: 'Hospitals and clinics nearby' },
  quality_education: { emoji: '🎓', name: 'Quality Education', description: 'School quality and ratings' },
  housing_value: { emoji: '🏠', name: 'Housing Value', description: 'Market trends and pricing' }
}

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
        if (response.coordinates) {
          set_coordinates(response.coordinates)
        }

        // Animate pillar completion in a deterministic order to keep the UX engaging.
        const pillarOrder = Object.keys(PILLAR_CONFIG)
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
          set_final_score(response.total_score)
          setTimeout(() => {
            if (!cancelled) on_complete(response)
          }, 500)
        }, totalAnimationMs)
      } catch (e) {
        if (cancelled) return
        const err = e instanceof Error ? e : new Error('Unknown error')
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
    <div className="flex h-full w-full bg-homefit-bg-secondary" style={{ minHeight: '100vh', width: '100%', position: 'relative' }}>
      {/* Main content - always render so map can initialize */}
      <div className="flex h-full w-full" style={{ minHeight: '100vh' }}>
        {/* Left side - Map */}
        <div 
          className="w-1/2 border-r border-gray-200" 
          style={{ 
            minHeight: '100vh', 
            height: '100vh',
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
        <div className="w-1/2 p-8 overflow-y-auto bg-white" style={{ minHeight: '100vh', position: 'relative' }}>
          {/* Loading overlay - only on right side */}
          {status === 'starting' && (
            <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
              <div className="text-center max-w-md px-4">
                <div className="text-2xl font-bold text-homefit-text-primary mb-2">Initializing...</div>
                <div className="text-sm text-homefit-text-secondary mb-6">Preparing to analyze {location}</div>
                <LoadingQuotes is_loading={true} />
              </div>
            </div>
          )}
          
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-homefit-text-primary mb-4">Analyzing {location}</h2>
            
            <ProgressBar progress={progress} />
            
            <div className="mb-6">
              <LoadingQuotes is_loading={status !== 'complete'} />
            </div>
            
            {final_score !== null && (
              <div className="mb-6 p-6 bg-homefit-score-high/10 border-2 border-homefit-score-high/30 rounded-lg">
                <div className="text-center">
                  <div className="text-4xl font-bold text-homefit-score-high mb-2">{final_score.toFixed(1)}</div>
                  <div className="text-sm text-homefit-score-high">Final Score</div>
                </div>
              </div>
            )}
            
            {current_pillar && status === 'analyzing' && (
              <CurrentlyAnalyzing 
                pillar_key={current_pillar}
                config={PILLAR_CONFIG[current_pillar]}
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
