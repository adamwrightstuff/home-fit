'use client'

import { useState } from 'react'
import { ScoreResponse } from '@/types/api'
import LocationSearch from '@/components/LocationSearch'
import SearchOptionsComponent, { DEFAULT_PRIORITIES, type SearchOptions, type PillarPriorities } from '@/components/SearchOptions'
import ScoreDisplay from '@/components/ScoreDisplay'
import SmartLoadingScreen from '@/components/SmartLoadingScreen'
import ErrorMessage from '@/components/ErrorMessage'
import PlaceValuesGame from '@/components/PlaceValuesGame'
import TokenWeightsGame from '@/components/TokenWeightsGame'
import AppHeader from '@/components/AppHeader'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

type WeightingMode = 'priorities' | 'tokens'

const TOKENS_STORAGE_KEY = 'homefit_tokens'
const WEIGHTING_MODE_STORAGE_KEY = 'homefit_weighting_mode'

export default function Home() {
  const [score_data, set_score_data] = useState<ScoreResponse | null>(null)
  const [loading, set_loading] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const [request_start_time, set_request_start_time] = useState<number | undefined>(undefined)
  const [current_location, set_current_location] = useState<string>('')
  const [show_game, set_show_game] = useState(false)
  const [show_token_game, set_show_token_game] = useState(false)
  const [search_options_expanded, set_search_options_expanded] = useState(false)
  const [weighting_mode, set_weighting_mode] = useState<WeightingMode>(() => {
    try {
      const v = sessionStorage.getItem(WEIGHTING_MODE_STORAGE_KEY)
      if (v === 'tokens' || v === 'priorities') return v
    } catch {
      // ignore
    }
    return 'priorities'
  })
  const [tokens, set_tokens] = useState<string | undefined>(() => {
    try {
      const v = sessionStorage.getItem(TOKENS_STORAGE_KEY)
      return v || undefined
    } catch {
      return undefined
    }
  })
  // Initialize from sessionStorage if available, otherwise use defaults
  // This ensures quiz priorities persist across page reloads
  const [search_options, set_search_options] = useState<SearchOptions>(() => {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const parsed = JSON.parse(stored)
        return {
          priorities: parsed.priorities || { ...DEFAULT_PRIORITIES },
          include_chains: parsed.include_chains !== undefined ? parsed.include_chains : true,
          // Premium-gated: default OFF unless explicitly enabled by user with a premium code
          enable_schools: parsed.enable_schools !== undefined ? parsed.enable_schools : false,
          job_categories: Array.isArray(parsed.job_categories) ? parsed.job_categories : [],
        }
      }
    } catch (e) {
      // Ignore errors, fall back to defaults
    }
    return {
      priorities: { ...DEFAULT_PRIORITIES },
      include_chains: true,
      enable_schools: false,
      job_categories: [],
    }
  })

  const handle_search = (location: string) => {
    console.log('Page: handle_search called with location:', location)
    set_loading(true)
    set_error(null)
    set_score_data(null)
    set_current_location(location)
    const start_time = Date.now()
    set_request_start_time(start_time)
    // Note: SmartLoadingScreen will handle the API call via streamScore
  }

  const handle_apply_priorities = (priorities: PillarPriorities) => {
    set_search_options(prev => {
      const updated = {
        ...prev,
        priorities
      }
      
      // Immediately save to sessionStorage to prevent SearchOptions from overwriting
      try {
        sessionStorage.setItem('homefit_search_options', JSON.stringify(updated))
      } catch (e) {
        // Ignore storage errors
      }
      
      return updated
    })
    set_show_game(false)
    set_search_options_expanded(true) // Expand the search options to show the applied priorities
    set_weighting_mode('priorities')
    try {
      sessionStorage.setItem(WEIGHTING_MODE_STORAGE_KEY, 'priorities')
    } catch {
      // ignore
    }
  }

  // Show game if active
  if (show_game) {
    return <PlaceValuesGame onApplyPriorities={handle_apply_priorities} onBack={() => set_show_game(false)} />
  }

  if (show_token_game) {
    return (
      <TokenWeightsGame
        enableSchools={search_options.enable_schools}
        initialTokens={tokens || null}
        onApplyTokens={(nextTokens) => {
          set_tokens(nextTokens)
          set_weighting_mode('tokens')
          try {
            sessionStorage.setItem(TOKENS_STORAGE_KEY, nextTokens)
            sessionStorage.setItem(WEIGHTING_MODE_STORAGE_KEY, 'tokens')
          } catch {
            // ignore
          }
          set_show_token_game(false)
          set_search_options_expanded(true)
        }}
        onBack={() => set_show_token_game(false)}
      />
    )
  }

  return (
    <main className="hf-page">
      <AppHeader
        tagline="Find the neighborhood where you truly belong"
        heroImageUrl="https://images.unsplash.com/photo-1653664346737-485ad147ab18?q=80&w=800&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
        heroImageAlt="Neighborhood street with homes"
      />
      <div className="hf-container">

        <div id="search" className="hf-card">
          <LocationSearch onSearch={handle_search} disabled={loading} />
          <SearchOptionsComponent 
            options={search_options} 
            onChange={set_search_options}
            disabled={loading}
            expanded={search_options_expanded}
            onExpandedChange={set_search_options_expanded}
          />
          <div style={{ marginTop: '1.25rem' }} className="hf-panel">
            <div className="hf-label" style={{ marginBottom: '0.5rem' }}>
              Weighting mode
            </div>
            <div className="hf-muted" style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>
              Choose how you want to personalize your score. Coin weights use a 20‑coin budget (5% per coin).
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className={weighting_mode === 'priorities' ? 'hf-btn-primary' : 'hf-btn-link'}
                  onClick={() => {
                    set_weighting_mode('priorities')
                    try {
                      sessionStorage.setItem(WEIGHTING_MODE_STORAGE_KEY, 'priorities')
                    } catch {
                      // ignore
                    }
                  }}
                  style={weighting_mode === 'priorities' ? undefined : { border: '1px solid var(--hf-border)', color: 'var(--hf-text-primary)' }}
                >
                  Use priorities
                </button>
                <button
                  type="button"
                  className={weighting_mode === 'tokens' ? 'hf-btn-primary' : 'hf-btn-link'}
                  onClick={() => {
                    if (!tokens) {
                      set_show_token_game(true)
                      return
                    }
                    set_weighting_mode('tokens')
                    try {
                      sessionStorage.setItem(WEIGHTING_MODE_STORAGE_KEY, 'tokens')
                    } catch {
                      // ignore
                    }
                  }}
                  style={weighting_mode === 'tokens' ? undefined : { border: '1px solid var(--hf-border)', color: 'var(--hf-text-primary)' }}
                >
                  Use coin weights
                </button>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => set_show_token_game(true)}
                  className="hf-btn-primary"
                >
                  {tokens ? 'Edit coin weights' : 'Play coin game'}
                </button>
                <button
                  type="button"
                  onClick={() => set_show_game(true)}
                  className="hf-btn-link"
                  style={{ border: '1px solid var(--hf-border)', color: 'var(--hf-text-primary)' }}
                >
                  Take quiz
                </button>
              </div>
            </div>
            <div className="hf-muted" style={{ fontSize: '0.92rem', marginTop: '0.75rem' }}>
              {tokens ? (
                <>
                  Coin weights saved. {weighting_mode === 'tokens' ? <strong>Currently using coin weights.</strong> : 'Switch to “Use coin weights” to apply them.'}
                </>
              ) : (
                <>No coin weights yet.</>
              )}
            </div>
          </div>
        </div>

        {!loading && !score_data && !error && (
          <section style={{ marginTop: '3rem', marginBottom: '3rem' }}>
            <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
              <div className="hf-section-title" style={{ marginBottom: '0.5rem' }}>
                10 Essential Livability Factors
              </div>
              <div className="hf-muted">We analyze every location across these key pillars.</div>
            </div>

            <div className="hf-grid-3">
              {(
                [
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
                ] as PillarKey[]
              ).map((key) => (
                <div key={key} className="hf-card-sm" style={{ cursor: 'default' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>{PILLAR_META[key].icon}</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--hf-text-primary)', marginBottom: '0.35rem' }}>
                    {PILLAR_META[key].name}
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
                    {PILLAR_META[key].description}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {loading && current_location && (
          <div className="fixed inset-0 z-50 hf-page hf-viewport">
            <SmartLoadingScreen
              location={current_location}
              priorities={weighting_mode === 'priorities' ? JSON.stringify(search_options.priorities) : undefined}
              tokens={weighting_mode === 'tokens' ? tokens : undefined}
              job_categories={search_options.job_categories?.join(',') || undefined}
              include_chains={search_options.include_chains}
              enable_schools={search_options.enable_schools}
              on_complete={(response) => {
                set_score_data(response)
                set_loading(false)
                set_request_start_time(undefined)
              }}
              on_error={(error) => {
                set_error(error.message)
                set_loading(false)
                set_request_start_time(undefined)
              }}
            />
          </div>
        )}

        {!loading && error && (
          <div className="hf-card">
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
