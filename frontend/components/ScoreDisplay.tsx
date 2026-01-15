'use client'

import { useState } from 'react'
import { ScoreResponse } from '@/types/api'
import TotalScore from './TotalScore'
import PillarCard from './PillarCard'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

interface ScoreDisplayProps {
  data: ScoreResponse
}

const PILLAR_ORDER: PillarKey[] = [
  'natural_beauty',
  'built_beauty',
  'neighborhood_amenities',
  'active_outdoors',
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'quality_education',
  'housing_value',
]

export default function ScoreDisplay({ data }: ScoreDisplayProps) {
  const { location_info, total_score, livability_pillars, overall_confidence, metadata } = data
  const [copied, setCopied] = useState(false)

  // Copy scores summary to clipboard
  const copyScores = async () => {
    const lines = [
      `HomeFit Livability Score: ${location_info.city}, ${location_info.state} ${location_info.zip}`,
      `Total Score: ${total_score.toFixed(1)}/100`,
      '',
      'Pillar Scores:',
      ...PILLAR_ORDER.map((key) => `  ${PILLAR_META[key].name}: ${livability_pillars[key].score.toFixed(1)}/100`),
    ]
    
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div style={{ marginTop: '1.5rem', display: 'grid', gap: '1.5rem' }}>
      <div className="hf-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ minWidth: 260 }}>
            <div className="hf-label" style={{ marginBottom: '0.25rem' }}>
              Score summary for
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--hf-text-primary)' }}>
              {location_info.city}, {location_info.state} {location_info.zip}
            </div>
            <div className="hf-muted" style={{ marginTop: '0.5rem' }}>
              Input: {data.input}
            </div>
            <div className="hf-muted" style={{ marginTop: '0.25rem', fontSize: '0.95rem' }}>
              Coordinates: {data.coordinates.lat.toFixed(6)}, {data.coordinates.lon.toFixed(6)}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <button
              onClick={copyScores}
              className="hf-btn-primary"
              style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem' }}
            >
              {copied ? 'Copied!' : 'Copy scores'}
            </button>
            <a className="hf-btn-link" href="#search">
              Search another location
            </a>
          </div>
        </div>

        <div className="hf-grid-2" style={{ marginTop: '2rem' }}>
          <TotalScore score={total_score} confidence={overall_confidence} />
          <div className="hf-panel">
            <div className="hf-label" style={{ marginBottom: '0.75rem' }}>
              What this means
            </div>
            <div className="hf-muted">
              Your HomeFit score combines 9 pillar scores (0–100) using your priority weights. Higher-priority pillars contribute more to your total.
            </div>

            <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--hf-border)' }}>
              <div className="hf-label" style={{ marginBottom: '0.5rem' }}>
                Data notes
              </div>
              <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
                API version: {metadata.version}
                {metadata.cache_hit ? ' (cached)' : ''}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div className="hf-section-title" style={{ marginBottom: '1rem' }}>
          Pillar scores
        </div>
        <div className="hf-grid-3">
          {PILLAR_ORDER.map((key) => (
            <PillarCard key={key} pillar_key={key} pillar={livability_pillars[key]} />
          ))}
        </div>
      </div>
    </div>
  )
}
