'use client'

import { useState } from 'react'
import { getScore, ScoreRequestParams } from '@/lib/api'
import { ScoreResponse } from '@/types/api'
import LocationSearch from '@/components/LocationSearch'
import ScoreDisplay from '@/components/ScoreDisplay'
import LoadingSpinner from '@/components/LoadingSpinner'
import ErrorMessage from '@/components/ErrorMessage'

export default function Home() {
  const [scoreData, setScoreData] = useState<ScoreResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (location: string) => {
    setLoading(true)
    setError(null)
    setScoreData(null)

    try {
      const params: ScoreRequestParams = {
        location,
        include_chains: true,
        enable_schools: true,
      }
      const data = await getScore(params)
      setScoreData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
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
          <LocationSearch onSearch={handleSearch} disabled={loading} />
        </div>

        {loading && (
          <div className="bg-white rounded-lg shadow-lg p-8">
            <LoadingSpinner />
          </div>
        )}

        {error && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <ErrorMessage message={error} />
          </div>
        )}

        {scoreData && !loading && (
          <ScoreDisplay data={scoreData} />
        )}
      </div>
    </main>
  )
}
