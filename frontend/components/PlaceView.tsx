'use client'

import { useState, useCallback } from 'react'
import InteractiveMap from './InteractiveMap'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'
import { getScoreSinglePillar } from '@/lib/api'
import { totalFromPartialPillarScores } from '@/lib/reweight'
import type { GeocodeResult } from '@/types/api'
import type { SearchOptions } from './SearchOptions'
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

export interface PlaceViewProps {
  place: GeocodeResult & { location: string }
  searchOptions: SearchOptions
  onError: (message: string) => void
  onBack: () => void
}

export default function PlaceView({ place, searchOptions, onError, onBack }: PlaceViewProps) {
  const [pillarScores, setPillarScores] = useState<Record<string, { score: number }>>({})
  const [loadingPillar, setLoadingPillar] = useState<string | null>(null)

  const runningTotal = totalFromPartialPillarScores(
    Object.fromEntries(Object.entries(pillarScores).map(([k, v]) => [k, v.score])),
    searchOptions.priorities
  )
  const completedCount = Object.keys(pillarScores).length

  const scorePillar = useCallback(
    async (pillar: string) => {
      if (pillarScores[pillar] != null || loadingPillar !== null) return
      setLoadingPillar(pillar)
      try {
        const resp = await getScoreSinglePillar({
          location: place.location,
          pillar,
          priorities: JSON.stringify(searchOptions.priorities),
          job_categories: searchOptions.job_categories?.join(','),
          include_chains: searchOptions.include_chains,
          enable_schools: searchOptions.enable_schools,
        })
        const pillars = (resp.livability_pillars as unknown as Record<string, { score?: number }>) || {}
        const data = pillars[pillar]
        if (data != null && typeof data.score === 'number') {
          setPillarScores((prev) => ({ ...prev, [pillar]: { score: data.score! } }))
        }
      } catch (e) {
        onError(e instanceof Error ? e.message : 'Failed to load this score.')
      } finally {
        setLoadingPillar(null)
      }
    },
    [place.location, searchOptions, pillarScores, loadingPillar, onError]
  )

  return (
    <div className="hf-card" style={{ marginTop: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <div className="hf-label" style={{ marginBottom: '0.25rem' }}>Location</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
            {place.display_name || place.location}
          </div>
          <div className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Tap any pillar below to get its score. Total updates as you go.
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

      {/* Running total */}
      {completedCount > 0 && (
        <div className="hf-panel" style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
          <div className="hf-muted" style={{ fontSize: '0.9rem', marginBottom: '0.25rem' }}>
            Score so far ({completedCount} of {PILLAR_ORDER.length} pillars)
          </div>
          <div className="hf-score-hero" style={{ display: 'inline-block', padding: '1rem 1.5rem', borderRadius: 16 }}>
            <div className="hf-score-hero__value" style={{ fontSize: '2.25rem' }}>
              {runningTotal != null ? runningTotal.toFixed(1) : '—'}
            </div>
            <div className="hf-score-hero__label">Running total</div>
          </div>
        </div>
      )}

      {/* Pillar list - tap to score */}
      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {PILLAR_ORDER.map((key) => {
          const score = pillarScores[key]
          const loading = loadingPillar === key
          const meta = PILLAR_META[key]
          return (
            <button
              key={key}
              type="button"
              onClick={() => scorePillar(key)}
              disabled={loading}
              className="hf-panel"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '1rem',
                padding: '1rem 1.25rem',
                textAlign: 'left',
                border: '1px solid var(--hf-border)',
                borderRadius: 12,
                cursor: loading ? 'wait' : 'pointer',
                background: score != null ? 'var(--hf-bg-subtle)' : undefined,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: 0 }}>
                <span style={{ fontSize: '1.75rem' }}>{meta.icon}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>{meta.name}</div>
                  <div className="hf-muted" style={{ fontSize: '0.85rem' }}>{meta.description}</div>
                </div>
              </div>
              <div style={{ flexShrink: 0 }}>
                {loading && (
                  <span className="hf-muted" style={{ fontSize: '0.9rem' }}>Scoring…</span>
                )}
                {!loading && score != null && (
                  <span className={getScoreBadgeClass(score.score)} style={{ padding: '0.35rem 0.75rem', borderRadius: 8 }}>
                    {score.score.toFixed(0)}
                  </span>
                )}
                {!loading && score == null && (
                  <span className="hf-muted" style={{ fontSize: '0.9rem' }}>Tap to score</span>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
