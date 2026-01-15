'use client'

import { useState } from 'react'
import { LivabilityPillar } from '@/types/api'
import { PILLAR_META, getScoreBadgeClass, type PillarKey } from '@/lib/pillars'

interface PillarCardProps {
  pillar_key: PillarKey
  pillar: LivabilityPillar
}

export default function PillarCard({ pillar_key, pillar }: PillarCardProps) {
  const [expanded, setExpanded] = useState(false)
  const meta = PILLAR_META[pillar_key]

  return (
    <div
      className="hf-card-sm"
      role="button"
      tabIndex={0}
      onClick={() => setExpanded((v) => !v)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') setExpanded((v) => !v)
      }}
      style={{ cursor: 'pointer' }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center' }}>
          <div style={{ fontSize: '1.6rem' }}>{meta.icon}</div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--hf-text-primary)' }}>{meta.name}</div>
            <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
              {meta.description}
            </div>
          </div>
        </div>
        <div className={getScoreBadgeClass(pillar.score)}>{pillar.score.toFixed(0)}</div>
      </div>

      <div style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '0.75rem' }}>
        <div>
          <div className="hf-label">Weight</div>
          <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)' }}>{pillar.weight.toFixed(1)}%</div>
        </div>
        <div>
          <div className="hf-label">Contribution</div>
          <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)' }}>{pillar.contribution.toFixed(1)}</div>
        </div>
        <div>
          <div className="hf-label">Confidence</div>
          <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)' }}>{pillar.confidence.toFixed(0)}%</div>
        </div>
      </div>

      <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          className="hf-btn-link"
          onClick={(e) => {
            e.stopPropagation()
            setExpanded((v) => !v)
          }}
        >
          {expanded ? 'Hide' : 'Show'} details
        </button>
      </div>

      {expanded ? (
        <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--hf-border)' }}>
          <div className="hf-label" style={{ marginBottom: '0.5rem' }}>
            Details
          </div>

          <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
            {pillar.data_quality?.quality_tier ? (
              <div style={{ marginBottom: '0.75rem' }}>
                Data quality: <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)', textTransform: 'capitalize' }}>{pillar.data_quality.quality_tier}</span>
              </div>
            ) : null}

            {pillar.summary && Object.keys(pillar.summary).length > 0 ? (
              <div style={{ display: 'grid', gap: '0.75rem' }}>
                {Object.entries(pillar.summary).map(([key, value]) => {
                  // Nested objects (e.g., Active Outdoors summary)
                  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    return (
                      <div key={key}>
                        <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)', textTransform: 'capitalize', marginBottom: '0.25rem' }}>
                          {key.replace(/_/g, ' ')}
                        </div>
                        <div style={{ display: 'grid', gap: '0.35rem', paddingLeft: '0.75rem' }}>
                          {Object.entries(value).map(([subKey, subValue]) => (
                            <div key={subKey} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                              <span style={{ textTransform: 'capitalize' }}>{subKey.replace(/_/g, ' ')}</span>
                              <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>
                                {typeof subValue === 'number'
                                  ? subValue % 1 === 0
                                    ? subValue.toString()
                                    : subValue.toFixed(2)
                                  : subValue === null || subValue === undefined
                                    ? 'N/A'
                                    : String(subValue)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  }

                  // Arrays: show as comma-separated
                  if (Array.isArray(value)) {
                    return (
                      <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                        <span style={{ textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</span>
                        <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)', textAlign: 'right' }}>
                          {value.length ? value.map((v) => String(v)).join(', ') : '—'}
                        </span>
                      </div>
                    )
                  }

                  // Simple values
                  return (
                    <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                      <span style={{ textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</span>
                      <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>
                        {typeof value === 'number'
                          ? value % 1 === 0
                            ? value.toString()
                            : value.toFixed(2)
                          : value === null || value === undefined
                            ? 'N/A'
                            : String(value)}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div>No additional details available.</div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
