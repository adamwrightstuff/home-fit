'use client'

import { useMemo, useState } from 'react'
import { ScoreResponse } from '@/types/api'
import type { GeocodeResult } from '@/types/api'
import LocationSearch from '@/components/LocationSearch'
import SearchOptionsComponent, { DEFAULT_PRIORITIES, type SearchOptions, type PillarPriorities } from '@/components/SearchOptions'
import ScoreDisplay from '@/components/ScoreDisplay'
import ErrorMessage from '@/components/ErrorMessage'
import PlaceValuesGame from '@/components/PlaceValuesGame'
import PlaceView from '@/components/PlaceView'
import AppHeader from '@/components/AppHeader'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { getGeocode } from '@/lib/api'

export default function Home() {
  const [score_data, set_score_data] = useState<ScoreResponse | null>(null)
  const [loading, set_loading] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const [place, set_place] = useState<(GeocodeResult & { location: string }) | null>(null)
  const [show_game, set_show_game] = useState(false)
  // Search options (priorities, job_categories, etc.) for scoring; persisted for quiz and PlaceView
  const [search_options, set_search_options] = useState<SearchOptions>(() => {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const parsed = JSON.parse(stored)
        return {
          priorities: parsed.priorities || { ...DEFAULT_PRIORITIES },
          include_chains: parsed.include_chains !== undefined ? parsed.include_chains : true,
          enable_schools: parsed.enable_schools !== undefined ? parsed.enable_schools : false,
          job_categories: Array.isArray(parsed.job_categories) ? parsed.job_categories : [],
        }
      }
    } catch (e) {
      // ignore
    }
    return {
      priorities: { ...DEFAULT_PRIORITIES },
      include_chains: true,
      enable_schools: false,
      job_categories: [],
    }
  })

  const display_score_data = useMemo(() => {
    if (!score_data) return null
    return reweightScoreResponseFromPriorities(score_data, search_options.priorities)
  }, [score_data, search_options.priorities])

  const handle_search = (location: string) => {
    set_loading(true)
    set_error(null)
    set_score_data(null)
    set_place(null)
    getGeocode(location)
      .then((geo) => {
        set_place({ ...geo, location })
        set_loading(false)
      })
      .catch((err) => {
        set_error(err instanceof Error ? err.message : 'Could not find that location.')
        set_loading(false)
      })
  }

  const handle_apply_priorities = (priorities: PillarPriorities) => {
    set_search_options(prev => {
      const updated = { ...prev, priorities }
      try {
        sessionStorage.setItem('homefit_search_options', JSON.stringify(updated))
      } catch (e) {
        // ignore
      }
      return updated
    })
    set_show_game(false)
  }

  if (show_game) {
    return <PlaceValuesGame onApplyPriorities={handle_apply_priorities} onBack={() => set_show_game(false)} />
  }

  // Page 1: Landing / Search — hero, search bar, Take quiz only. No pillar grid.
  if (!place && !score_data) {
    return (
      <main className="hf-page">
        <AppHeader
          tagline="Where are you thinking of moving?"
          heroImageUrl="https://images.unsplash.com/photo-1653664346737-485ad147ab18?q=80&w=800&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
          heroImageAlt="Neighborhood street with homes"
        />
        <div className="hf-container">
          <div id="search" className="hf-card">
            <LocationSearch onSearch={handle_search} disabled={loading} />
            <div style={{ marginTop: '1.25rem' }} className="hf-panel">
              <button
                type="button"
                onClick={() => set_show_game(true)}
                className="hf-btn-secondary"
                style={{ width: '100%' }}
              >
                Take quiz
              </button>
            </div>
          </div>

          {loading && (
            <div className="hf-card" style={{ marginTop: '1.5rem', padding: '2rem', textAlign: 'center' }}>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--hf-text-primary)', marginBottom: '0.5rem' }}>
                Finding location…
              </div>
              <div className="hf-muted">Geocoding your place and preparing the map.</div>
            </div>
          )}

          {!loading && error && (
            <div className="hf-card" style={{ marginTop: '1.5rem' }}>
              <ErrorMessage message={error} />
            </div>
          )}
        </div>
      </main>
    )
  }

  // Page 2: Score this location — location + map, quiz CTA, pillar grid, sticky Run Score
  if (place && !score_data) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <PlaceView
            place={place}
            searchOptions={search_options}
            onError={(msg) => set_error(msg)}
            onBack={() => { set_place(null); set_error(null) }}
            onTakeQuiz={() => set_show_game(true)}
          />
          {place && error && (
            <div className="hf-card" style={{ marginTop: '1rem' }}>
              <ErrorMessage message={error} />
            </div>
          )}
        </div>
      </main>
    )
  }

  // After scoring: show results; "Search another location" resets to Page 1
  const handleSearchAnother = () => {
    set_place(null)
    set_score_data(null)
    set_error(null)
  }

  return (
    <main className="hf-page">
      <div className="hf-container">
        {score_data && (
          <ScoreDisplay
            data={display_score_data || score_data}
            onSearchAnother={handleSearchAnother}
          />
        )}
      </div>
    </main>
  )
}
