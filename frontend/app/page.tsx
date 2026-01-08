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
  }

  // Show game if active
  if (show_game) {
    return <PlaceValuesGame onApplyPriorities={handle_apply_priorities} />
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-2">
            HomeFit
          </h1>
          <p className="text-lg text-gray-600">
            Discover how livable a location is across 9 key pillars
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <LocationSearch onSearch={handle_search} disabled={loading} />
          <div className="mt-4 mb-4">
            <button
              onClick={() => set_show_game(true)}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg font-medium hover:from-purple-700 hover:to-indigo-700 transition-all flex items-center justify-center gap-2 shadow-sm"
            >
              <Sparkles className="w-4 h-4" />
              Discover Your Place Values (20-question quiz)
            </button>
            <p className="text-xs text-gray-500 text-center mt-2">
              Not sure what matters most? Take our quick quiz to personalize your priorities
            </p>
          </div>
          <SearchOptionsComponent 
            options={search_options} 
            onChange={set_search_options}
            disabled={loading}
          />
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
