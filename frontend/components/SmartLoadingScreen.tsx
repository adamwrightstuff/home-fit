'use client'

import { useEffect, useState } from 'react'
import { StreamEvent, streamScore } from '@/lib/api'
import { ScoreResponse } from '@/types/api'
import CurrentlyAnalyzing from './CurrentlyAnalyzing'
import CompletedPillars from './CompletedPillars'
import ProgressBar from './ProgressBar'
import InteractiveMap from './InteractiveMap'

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
    console.log('SmartLoadingScreen: Starting stream for location:', location)
    const cleanup = streamScore(
      { 
        location,
        priorities,
        include_chains,
        enable_schools
      },
      (event: StreamEvent) => {
        console.log('SmartLoadingScreen: Received event:', event.status, event)
        if (event.status === 'started') {
          console.log('SmartLoadingScreen: Setting status to starting')
          set_status('starting')
        } else if (event.status === 'analyzing') {
          console.log('SmartLoadingScreen: Setting status to analyzing, coordinates:', event.coordinates)
          set_status('analyzing')
          if (event.coordinates) {
            set_coordinates(event.coordinates)
          }
        } else if (event.status === 'complete' && event.pillar) {
          set_completed_pillars((prev) => {
            const new_completed = new Map(prev)
            new_completed.set(event.pillar!, { 
              score: event.score || 0, 
              details: event 
            })
            
            // Calculate progress: each pillar is ~11.11% (100/9)
            const new_progress = (new_completed.size / 9) * 100
            set_progress(new_progress)
            
            return new_completed
          })
          set_current_pillar(null) // Clear current pillar when it completes
        } else if (event.status === 'done' && event.response) {
          set_status('complete')
          set_progress(100)
          set_final_score(event.response.total_score)
          
          // Call on_complete after a brief delay to show final state
          setTimeout(() => {
            on_complete(event.response!)
          }, 500)
        } else if (event.status === 'error') {
          console.error('SmartLoadingScreen: Error event:', event)
          if (on_error) {
            on_error(new Error(event.message || 'Unknown error'))
          }
        }
      },
      (error) => {
        console.error('SmartLoadingScreen: Stream error:', error)
        if (on_error) {
          on_error(error)
        }
      }
    )

    return cleanup
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

  console.log('SmartLoadingScreen: Rendering with status:', status, 'progress:', progress, 'location:', location)
  
  return (
    <div className="flex h-full w-full bg-gray-50" style={{ minHeight: '100vh', width: '100%', position: 'relative' }}>
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
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-700 mb-2">Initializing...</div>
                <div className="text-sm text-gray-500">Preparing to analyze {location}</div>
              </div>
            </div>
          )}
          
          <div className="max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Analyzing {location}</h2>
            
            <ProgressBar progress={progress} />
            
            {final_score !== null && (
              <div className="mb-6 p-6 bg-green-50 border-2 border-green-200 rounded-lg">
                <div className="text-center">
                  <div className="text-4xl font-bold text-green-700 mb-2">{final_score.toFixed(1)}</div>
                  <div className="text-sm text-green-600">Final Score</div>
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
