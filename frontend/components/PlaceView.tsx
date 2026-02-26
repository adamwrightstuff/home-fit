'use client'

import { useState, useCallback, useEffect } from 'react'
import InteractiveMap from './InteractiveMap'
import ProgressBar from './ProgressBar'
import { PILLAR_META, getScoreBadgeClass, getScoreBandLabel, getScoreBandColor, type PillarKey } from '@/lib/pillars'

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
  'climate_risk',
]

type Importance = 'Low' | 'Medium' | 'High'

/** Prefer neighborhood-style label: strip trailing zip so we show "Gowanus, Brooklyn" not "New York, NY 11217". */
function formatPlaceLabel(place: GeocodeResult & { location: string }): string {
  const name = place.display_name || place.location
  const withoutZip = name.replace(/,?\s*\d{5}(-\d{4})?$/, '').trim()
  if (withoutZip) return withoutZip
  return `${place.city}, ${place.state}`
}

const PREMIUM_CODE_KEY = 'homefit_premium_code'

export interface PlaceViewProps {
  place: GeocodeResult & { location: string }
  searchOptions: SearchOptions
  onSearchOptionsChange?: (options: SearchOptions) => void
  onError: (message: string) => void
  onBack: () => void
  onTakeQuiz?: () => void
}

export default function PlaceView({ place, searchOptions, onSearchOptionsChange, onError, onBack, onTakeQuiz }: PlaceViewProps) {
  const [selectedPillars, setSelectedPillars] = useState<Set<string>>(new Set())
  const [selectedPriorities, setSelectedPriorities] = useState<Record<string, Importance>>({})
  const [pillarScores, setPillarScores] = useState<Record<string, { score: number }>>({})
  const [totalScore, setTotalScore] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [scoreProgress, setScoreProgress] = useState<Record<string, { score: number }>>({})
  const [premiumCodeInput, setPremiumCodeInput] = useState('')
  const [savedPremiumCode, setSavedPremiumCode] = useState('')
  useEffect(() => {
    try {
      const v = window.sessionStorage?.getItem(PREMIUM_CODE_KEY) ?? ''
      setPremiumCodeInput(v)
      setSavedPremiumCode(v)
    } catch (_) {}
  }, [])

  const togglePillar = useCallback((key: string) => {
    setSelectedPillars((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
        setSelectedPriorities((p) => {
          const q = { ...p }
          delete q[key]
          return q
        })
      } else {
        next.add(key)
        setSelectedPriorities((p) => ({ ...p, [key]: 'Medium' }))
      }
      return next
    })
  }, [])

  const setPillarImportance = useCallback((key: string, level: Importance) => {
    setSelectedPriorities((prev) => ({ ...prev, [key]: level }))
  }, [])

  const runScore = useCallback(async () => {
    const selected = Array.from(selectedPillars)
    if (selected.length === 0) return
    setLoading(true)
    setProgress(5)
    setScoreProgress({})
    try {
      const prioritiesForRequest: PillarPriorities = {
        active_outdoors: 'None',
        built_beauty: 'None',
        natural_beauty: 'None',
        neighborhood_amenities: 'None',
        air_travel_access: 'None',
        public_transit_access: 'None',
        healthcare_access: 'None',
        economic_security: 'None',
        quality_education: 'None',
        housing_value: 'None',
        climate_risk: 'None',
      }
      selected.forEach((k) => {
        prioritiesForRequest[k as keyof PillarPriorities] = selectedPriorities[k] ?? 'Medium'
      })
      const resp = await getScoreWithProgress(
        {
          location: place.location,
          only: selected.join(','),
          priorities: JSON.stringify(prioritiesForRequest),
          job_categories: searchOptions.job_categories?.join(','),
          include_chains: searchOptions.include_chains,
          enable_schools: searchOptions.enable_schools,
        },
        (partial) => {
          setScoreProgress((prev) => ({ ...prev, ...partial }))
          const completed = Object.keys(partial).length
          const total = selected.length
          const pct = total > 0 ? Math.min(98, 5 + (completed / total) * 90) : 5
          setProgress(pct)
        }
      )
      const pillars = (resp.livability_pillars as unknown as Record<string, { score?: number }>) || {}
      const scores: Record<string, { score: number }> = {}
      selected.forEach((k) => {
        const data = pillars[k]
        if (data != null && typeof data.score === 'number') scores[k] = { score: data.score }
      })
      setPillarScores(scores)
      setTotalScore(typeof resp.total_score === 'number' ? resp.total_score : null)
      setProgress(100)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to run score.')
    } finally {
      setLoading(false)
      setProgress(0)
      setScoreProgress({})
    }
  }, [place.location, searchOptions, selectedPillars, selectedPriorities, onError])

  const hasResults = Object.keys(pillarScores).length > 0
  const locationLabel = formatPlaceLabel(place)

  return (
    <div className="hf-card" style={{ marginTop: '1.5rem', paddingBottom: '5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <div className="hf-label" style={{ marginBottom: '0.25rem' }}>Location</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
            {locationLabel}
          </div>
          <div className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Select pillars and set importance, then Run Score.
          </div>
        </div>
        <button type="button" onClick={onBack} className="hf-btn-link">
          Search another place
        </button>
      </div>

      {/* Map */}
      <div
        style={{
          width: '100%',
          height: '280px',
          borderRadius: 12,
          overflow: 'hidden',
          marginBottom: '1.5rem',
          background: 'var(--hf-bg-subtle)',
        }}
      >
        <InteractiveMap
          location={locationLabel}
          coordinates={{ lat: place.lat, lon: place.lon }}
          completed_pillars={Object.keys(pillarScores)}
        />
      </div>

      {/* Total score result */}
      {hasResults && totalScore != null && (
        <div className="hf-panel" style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
          <div className="hf-muted" style={{ fontSize: '0.9rem', marginBottom: '0.25rem' }}>Total score</div>
          <div className="hf-score-hero" style={{ display: 'inline-block', padding: '1rem 1.5rem', borderRadius: 16 }}>
            <div className="hf-score-hero__value" style={{ fontSize: '2.25rem' }}>{totalScore.toFixed(1)}</div>
            <div className="hf-score-hero__label">Weighted total</div>
          </div>
        </div>
      )}

      {/* Quiz CTA: collapsed at top of pillar grid */}
      {onTakeQuiz && (
        <div className="hf-panel" style={{ marginBottom: '1rem' }}>
          <button
            type="button"
            onClick={onTakeQuiz}
            className="hf-btn-link"
            style={{ width: '100%', textAlign: 'center', padding: '0.75rem' }}
          >
            Not sure what matters to you? Take the quiz
          </button>
        </div>
      )}

      {/* Pillar list: tap to select, importance only when selected */}
      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {PILLAR_ORDER.map((key) => {
          const selected = selectedPillars.has(key)
          const score = pillarScores[key]
          const importance = selectedPriorities[key] ?? 'Medium'
          const meta = PILLAR_META[key]
          return (
            <div
              key={key}
              role="button"
              tabIndex={0}
              onClick={() => togglePillar(key)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); togglePillar(key) } }}
              className="hf-panel"
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                padding: '1rem 1.25rem',
                border: `2px solid ${selected ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                borderRadius: 12,
                cursor: 'pointer',
                background: selected ? 'var(--hf-bg-subtle)' : undefined,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: 0 }}>
                  <span style={{ fontSize: '1.75rem' }}>{meta.icon}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>{meta.name}</div>
                    <div className="hf-muted" style={{ fontSize: '0.85rem' }}>{meta.description}</div>
                  </div>
                </div>
                <div style={{ flexShrink: 0 }}>
                  {score != null && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span className={getScoreBadgeClass(score.score)} style={{ padding: '0.35rem 0.75rem', borderRadius: 8 }}>
                        {score.score.toFixed(0)}
                      </span>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: getScoreBandColor(score.score) }}>
                        {getScoreBandLabel(score.score)}
                      </span>
                    </span>
                  )}
                  {score == null && selected && (
                    <span className="hf-muted" style={{ fontSize: '0.85rem' }}>Selected</span>
                  )}
                </div>
              </div>
              {selected && (
                <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span className="hf-muted" style={{ fontSize: '0.85rem', marginRight: '0.25rem' }}>Importance:</span>
                    {(['Low', 'Medium', 'High'] as const).map((level) => (
                      <button
                        key={level}
                        type="button"
                        onClick={() => setPillarImportance(key, level)}
                        style={{
                          padding: '0.35rem 0.65rem',
                          borderRadius: 8,
                          fontSize: '0.85rem',
                          fontWeight: importance === level ? 700 : 400,
                          background: importance === level ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                          color: importance === level ? 'white' : 'var(--hf-text-secondary)',
                          border: '1px solid var(--hf-border)',
                          cursor: 'pointer',
                        }}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                  {key === 'quality_education' && (
                    <div style={{ borderTop: '1px solid var(--hf-border)', paddingTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <label className="hf-muted" style={{ fontSize: '0.85rem' }}>Premium code (enables school scoring)</label>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                        <input
                          type="text"
                          value={premiumCodeInput}
                          onChange={(e) => setPremiumCodeInput(e.target.value)}
                          placeholder="Enter code"
                          className="hf-input"
                          disabled={loading}
                          style={{ flex: 1, minWidth: 140 }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const v = premiumCodeInput.trim()
                            setSavedPremiumCode(v)
                            try {
                              if (v) window.sessionStorage?.setItem(PREMIUM_CODE_KEY, v)
                              else window.sessionStorage?.removeItem(PREMIUM_CODE_KEY)
                            } catch (_) {}
                          }}
                          disabled={loading}
                          className="hf-premium-btn"
                        >
                          Save
                        </button>
                        {savedPremiumCode ? (
                          <button
                            type="button"
                            onClick={() => {
                              setPremiumCodeInput('')
                              setSavedPremiumCode('')
                              try { window.sessionStorage?.removeItem(PREMIUM_CODE_KEY) } catch (_) {}
                            }}
                            disabled={loading}
                            className="hf-premium-btn hf-premium-btn--outline"
                          >
                            Clear
                          </button>
                        ) : null}
                      </div>
                      {onSearchOptionsChange && (
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', cursor: 'pointer', marginTop: '0.25rem' }}>
                          <input
                            type="checkbox"
                            checked={searchOptions.enable_schools}
                            disabled={loading}
                            onChange={(e) => onSearchOptionsChange({ ...searchOptions, enable_schools: e.target.checked })}
                          />
                          <span style={{ color: 'var(--hf-text-primary)' }}>Include school scoring</span>
                        </label>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Sticky Run Score at bottom */}
      <div
        style={{
          position: 'sticky',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '1rem 0',
          marginTop: '1rem',
          marginLeft: '-2.5rem',
          marginRight: '-2.5rem',
          marginBottom: '-2.5rem',
          paddingLeft: '2.5rem',
          paddingRight: '2.5rem',
          paddingBottom: '2.5rem',
          background: 'var(--hf-card-bg)',
          borderTop: '1px solid var(--hf-border)',
          boxShadow: '0 -4px 20px rgba(0,0,0,0.06)',
        }}
      >
        {loading && (
          <div style={{ marginBottom: '1rem' }}>
            <ProgressBar progress={progress} />
            <div className="hf-muted" style={{ fontSize: '0.875rem', marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.35rem 0.75rem', alignItems: 'center' }}>
              {Object.keys(scoreProgress).length === 0 ? (
                <span>Preparing location and shared data…</span>
              ) : (
                PILLAR_ORDER.filter((k) => selectedPillars.has(k)).map((key) => {
                  const meta = PILLAR_META[key]
                  const done = key in scoreProgress
                  return (
                    <span key={key} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                      {done ? (
                        <>
                          <span style={{ color: 'var(--hf-success, #22c55e)' }} aria-hidden>✓</span>
                          <span>{meta.icon} {meta.name}</span>
                        </>
                      ) : (
                        <span style={{ opacity: 0.85 }}>{meta.icon} {meta.name}…</span>
                      )}
                    </span>
                  )
                })
              )}
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={runScore}
          disabled={selectedPillars.size === 0 || loading}
          className="hf-btn-primary"
          style={{ width: '100%', padding: '1rem 1.5rem', fontSize: '1.1rem' }}
        >
          {loading ? 'Scoring…' : `Run Score${selectedPillars.size > 0 ? ` (${selectedPillars.size} pillar${selectedPillars.size === 1 ? '' : 's'})` : ''}`}
        </button>
      </div>
    </div>
  )
}
