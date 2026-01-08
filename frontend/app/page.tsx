'use client'

import { useState } from 'react'
import { getScore } from '@/lib/api'
import { ScoreResponse, ScoreRequestParams } from '@/types/api'
import LocationSearch from '@/components/LocationSearch'
import SearchOptionsComponent, { DEFAULT_PRIORITIES, type SearchOptions, type PillarPriorities } from '@/components/SearchOptions'
import ScoreDisplay from '@/components/ScoreDisplay'
import LoadingSpinner from '@/components/LoadingSpinner'
import ErrorMessage from '@/components/ErrorMessage'
import PlaceValuesGame from '@/components/PlaceValuesGame'
import { Sparkles } from 'lucide-react'

export default function Home() {
  const [score_data, set_score_data] = useState<ScoreResponse | null>(null)
  const [loading, set_loading] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const [request_start_time, set_request_start_time] = useState<number | undefined>(undefined)
  const [show_game, set_show_game] = useState(false)
  const [search_options_expanded, set_search_options_expanded] = useState(false)
  const [search_options, set_search_options] = useState<SearchOptions>({
    priorities: { ...DEFAULT_PRIORITIES },
    include_chains: true,
    enable_schools: true,
  })

  const handle_search = async (location: string) => {
    set_loading(true)
    set_error(null)
    set_score_data(null)
    const start_time = Date.now()
    set_request_start_time(start_time)

    try {
      const params: ScoreRequestParams = {
        location,
        priorities: JSON.stringify(search_options.priorities),
        include_chains: search_options.include_chains,
        enable_schools: search_options.enable_schools,
      }
      const data = await getScore(params)
      set_score_data(data)
    } catch (err) {
      set_error(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      set_loading(false)
      set_request_start_time(undefined)
    }
  }

  const handle_apply_priorities = (priorities: PillarPriorities) => {
    set_search_options(prev => ({
      ...prev,
      priorities
    }))
    set_show_game(false)
    set_search_options_expanded(true) // Expand the search options to show the applied priorities
  }

  // Show game if active
  if (show_game) {
    return <PlaceValuesGame onApplyPriorities={handle_apply_priorities} onBack={() => set_show_game(false)} />
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-2">
            HomeFit
          </h1>
          <p className="text-base md:text-lg text-gray-700 font-medium">
            Discover how livable a location is across 9 key pillars
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-xl p-6 md:p-8 mb-8">
          <LocationSearch onSearch={handle_search} disabled={loading} />
          <SearchOptionsComponent 
            options={search_options} 
            onChange={set_search_options}
            disabled={loading}
            expanded={search_options_expanded}
            onExpandedChange={set_search_options_expanded}
          />
          <div className="mt-6 pt-6 border-t border-gray-200">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1">
                <p className="text-sm text-gray-600 mb-1">
                  <span className="font-medium">Not sure what matters most?</span>
                </p>
                <p className="text-xs text-gray-500">
                  Take our 20-question quiz to discover your Place Values profile
                </p>
              </div>
              <button
                onClick={() => set_show_game(true)}
                className="flex-shrink-0 px-4 py-2.5 border-2 border-purple-200 text-purple-700 rounded-lg font-medium hover:bg-purple-50 hover:border-purple-300 hover:shadow-sm transition-all flex items-center gap-2 whitespace-nowrap focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
              >
                <Sparkles className="w-4 h-4" />
                Take Quiz
              </button>
            </div>
          </div>
        </div>

        {loading && (
          <div className="bg-white rounded-lg shadow-lg p-8">
            <LoadingSpinner startTime={request_start_time} />
          </div>
        )}

        {error && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <ErrorMessage message={error} />
          </div>
        )}

        {score_data && !loading && (
          <ScoreDisplay data={score_data} />
        )}
      </div>
    </main>
  )
}
