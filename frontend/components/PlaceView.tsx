'use client'

import { useState, useCallback } from 'react'
import InteractiveMap from './InteractiveMap'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'
import { getScore } from '@/lib/api'
import type { GeocodeResult } from '@/types/api'
import type { SearchOptions } from './SearchOptions'
import type { PillarPriorities } from './SearchOptions'
import { getScoreBadgeClass } from '@/lib/pillars'

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
]

type Importance = 'Low' | 'Medium' | 'High'

export interface PlaceViewProps {
  place: GeocodeResult & { location: string }
  searchOptions: SearchOptions
  onError: (message: string) => void
  onBack: () => void
}

export default function PlaceView({ place, searchOptions, onError, onBack }: PlaceViewProps) {
  const [selectedPillars, setSelectedPillars] = useState<Set<string>>(new Set())
  const [selectedPriorities, setSelectedPriorities] = useState<Record<string, Importance>>({})
  const [pillarScores, setPillarScores] = useState<Record<string, { score: number }>>({})
  const [totalScore, setTotalScore] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

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
      }
      selected.forEach((k) => {
        prioritiesForRequest[k as keyof PillarPriorities] = selectedPriorities[k] ?? 'Medium'
      })
      const resp = await getScore({
        location: place.location,
        only: selected.join(','),
        priorities: JSON.stringify(prioritiesForRequest),
        job_categories: searchOptions.job_categories?.join(','),
        include_chains: searchOptions.include_chains,
        enable_schools: searchOptions.enable_schools,
      })
      const pillars = (resp.livability_pillars as unknown as Record<string, { score?: number }>) || {}
      const scores: Record<string, { score: number }> = {}
      selected.forEach((k) => {
        const data = pillars[k]
        if (data != null && typeof data.score === 'number') scores[k] = { score: data.score }
      })
      setPillarScores(scores)
      setTotalScore(typeof resp.total_score === 'number' ? resp.total_score : null)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to run score.')
    } finally {
      setLoading(false)
    }
  }, [place.location, searchOptions, selectedPillars, selectedPriorities, onError])

  const hasResults = Object.keys(pillarScores).length > 0

  return (
    <div className="hf-card" style={{ marginTop: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <div className="hf-label" style={{ marginBottom: '0.25rem' }}>Location</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
            {place.display_name || place.location}
          </div>
          <div className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Tap pillars to select, set importance, then Run Score.
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
          location={place.location}
          coordinates={{ lat: place.lat, lon: place.lon }}
          completed_pillars={Object.keys(pillarScores)}
        />
      </div>

      {/* Run Score button */}
      <div style={{ marginBottom: '1.5rem' }}>
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
                    <span className={getScoreBadgeClass(score.score)} style={{ padding: '0.35rem 0.75rem', borderRadius: 8 }}>
                      {score.score.toFixed(0)}
                    </span>
                  )}
                  {score == null && selected && (
                    <span className="hf-muted" style={{ fontSize: '0.85rem' }}>Selected</span>
                  )}
                </div>
              </div>
              {selected && (
                <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
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
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
