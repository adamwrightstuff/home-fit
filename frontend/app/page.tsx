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
import { getGeocode, getScoreWithProgress } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { saveScore } from '@/lib/savedScores'

export default function Home() {
  const { user, isConfigured } = useAuth()
  const [score_data, set_score_data] = useState<ScoreResponse | null>(null)
  /** When user clicks "View results", we store payload + priorities so we can rehydrate Configure when they click "Edit pillars". */
  const [configureState, set_configure_state] = useState<{ payload: ScoreResponse; priorities: PillarPriorities } | null>(null)
  const [savedScoreId, setSavedScoreId] = useState<string | null>(null)
  const [loading, set_loading] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const [place, set_place] = useState<(GeocodeResult & { location: string }) | null>(null)
  const [show_game, set_show_game] = useState(false)
  /** When true, PlaceView should select all pillars and sync from applied quiz priorities. */
  const [justAppliedQuizPriorities, setJustAppliedQuizPriorities] = useState(false)
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
      natural_beauty_preference: Array.isArray(parsed.natural_beauty_preference) ? parsed.natural_beauty_preference : null,
      built_character_preference: ['historic', 'contemporary', 'no_preference'].includes(parsed.built_character_preference) ? parsed.built_character_preference : null,
      built_density_preference: ['spread_out_residential', 'walkable_residential', 'dense_urban_living'].includes(parsed.built_density_preference) ? parsed.built_density_preference : null,
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
      natural_beauty_preference: null,
      built_character_preference: null,
      built_density_preference: null,
    }
  })

  const display_score_data = useMemo(() => {
    if (!score_data) return null
    return reweightScoreResponseFromPriorities(score_data, configureState?.priorities ?? search_options.priorities)
  }, [score_data, configureState?.priorities, search_options.priorities])

  const handle_search = (location: string) => {
    set_loading(true)
    set_error(null)
    set_score_data(null)
    set_configure_state(null)
    set_place(null)
    setSavedScoreId(null)
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

  const handle_apply_priorities = (priorities: PillarPriorities, naturalBeautyPreference?: string[]) => {
    set_search_options(prev => {
      const updated = {
        ...prev,
        priorities,
        natural_beauty_preference: naturalBeautyPreference?.length ? naturalBeautyPreference : null,
      }
      try {
        sessionStorage.setItem('homefit_search_options', JSON.stringify(updated))
      } catch (e) {
        // ignore
      }
      return updated
    })
    setJustAppliedQuizPriorities(true)
    // Do not close quiz here; user closes via "Search a place" or Back (onBack).
  }

  if (show_game) {
    return <PlaceValuesGame onApplyPriorities={handle_apply_priorities} onBack={() => set_show_game(false)} />
  }

  // Page 1: Landing / Search — hero, search bar. No quiz here; quiz is after a location is searched.
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
          </div>

          {loading && (
            <div className="hf-card" style={{ marginTop: '1.5rem', padding: '2rem', textAlign: 'center' }}>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--hf-text-primary)', marginBottom: '0.5rem' }}>
                Finding location…
              </div>
              <div className="hf-muted">Geocoding your place and preparing the map. First search may take a moment if the server is waking up.</div>
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

  const handleSearchOptionsChange = (options: SearchOptions) => {
    set_search_options(options)
    try {
      sessionStorage.setItem('homefit_search_options', JSON.stringify(options))
    } catch (e) {
      // ignore
    }
  }

  // Page 2: Score this location — location + map, quiz CTA, pillar grid, sticky Run Score
  if (place && !score_data) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <PlaceView
            place={place}
            searchOptions={search_options}
            onSearchOptionsChange={handleSearchOptionsChange}
            onError={(msg) => set_error(msg)}
            onBack={() => { set_place(null); set_error(null) }}
            onTakeQuiz={() => set_show_game(true)}
            justAppliedQuizPriorities={justAppliedQuizPriorities}
            onAppliedQuizPrioritiesConsumed={() => setJustAppliedQuizPriorities(false)}
            onSave={async (payload, priorities) => {
              try {
                const { id } = await saveScore(payload, priorities)
                setSavedScoreId(id)
                return { id }
              } catch (e) {
                return { error: e instanceof Error ? e.message : 'Failed to save' }
              }
            }}
            onShowResults={(payload, priorities) => {
              set_score_data(payload)
              set_configure_state({ payload, priorities })
            }}
            initialPayload={configureState?.payload ?? null}
            initialPriorities={configureState?.priorities ?? null}
            isSignedIn={!!user}
            isAuthConfigured={isConfigured}
            savedScoreId={savedScoreId}
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
    set_configure_state(null)
    set_error(null)
  }

  const handleRunPillarScore = async (
    pillarKey: import('@/lib/pillars').PillarKey,
    options: import('@/components/ScoreDisplay').RunPillarScoreOptions
  ) => {
    if (!score_data) return
    const location = typeof score_data.input === 'string' && score_data.input.trim() ? score_data.input : [score_data.location_info?.city, score_data.location_info?.state, score_data.location_info?.zip].filter(Boolean).join(', ')
    if (!location) throw new Error('Missing location')
    const response = await getScoreWithProgress(
      {
        location,
        only: pillarKey,
        priorities: JSON.stringify(options.priorities),
        job_categories: options.job_categories?.length ? options.job_categories.join(',') : undefined,
        natural_beauty_preference: options.natural_beauty_preference?.length ? JSON.stringify(options.natural_beauty_preference) : undefined,
        built_character_preference: options.built_character_preference ?? undefined,
        built_density_preference: options.built_density_preference ?? undefined,
        include_chains: options.include_chains ?? true,
        enable_schools: options.enable_schools ?? false,
      },
      () => {}
    )
    const merged: ScoreResponse = {
      ...score_data,
      livability_pillars: {
        ...score_data.livability_pillars,
        [pillarKey]: (response.livability_pillars as unknown as Record<string, unknown>)[pillarKey],
      } as ScoreResponse['livability_pillars'],
      place_summary: response.place_summary ?? score_data.place_summary,
    }
    set_score_data(merged)
    set_configure_state({ payload: merged, priorities: options.priorities })
  }

  return (
    <main className="hf-page">
      <div className="hf-container">
        {score_data && (
          <ScoreDisplay
            data={display_score_data || score_data}
            onSearchAnother={handleSearchAnother}
            isSignedIn={!!user}
            isAuthConfigured={isConfigured}
            savedScoreId={savedScoreId}
            priorities={configureState?.priorities ?? search_options.priorities}
            onReconfigure={() => set_score_data(null)}
            onPrioritiesChange={(priorities) =>
              set_configure_state((prev) => (prev ? { ...prev, priorities } : null))
            }
            placeSummary={(display_score_data || score_data)?.place_summary ?? null}
            searchOptions={search_options}
            onRunPillarScore={handleRunPillarScore}
            onSave={async (payload, priorities) => {
              try {
                const { id } = await saveScore(payload, priorities)
                setSavedScoreId(id)
                return { id }
              } catch (e) {
                return { error: e instanceof Error ? e.message : 'Failed to save' }
              }
            }}
          />
        )}
      </div>
    </main>
  )
}
