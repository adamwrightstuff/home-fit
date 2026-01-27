'use client'

import { useState } from 'react'
import { LivabilityPillar } from '@/types/api'
import { PILLAR_META, getScoreBadgeClass, type PillarKey } from '@/lib/pillars'

interface PillarCardProps {
  pillar_key: PillarKey
  pillar: LivabilityPillar
}

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return 'N/A'
  return n % 1 === 0 ? n.toString() : n.toFixed(2)
}

function formatValue(value: any, depth: number = 0): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'number') return formatNumber(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.length ? value.map((v) => String(v)).join(', ') : '—'

  if (isRecord(value)) {
    // Common pattern in API: { count, types } for tier summaries
    const count = typeof value.count === 'number' ? value.count : null
    const types = Array.isArray(value.types) ? value.types : null
    if (count !== null && types) {
      const typeStr = types.length ? types.join(', ') : '—'
      return `${count} (${typeStr})`
    }

    // For small objects, render key=value pairs (avoid [object Object])
    if (depth < 2) {
      const entries = Object.entries(value)
        .filter(([, v]) => typeof v !== 'object' || v === null)
        .slice(0, 6)
      if (entries.length) {
        return entries.map(([k, v]) => `${k.replace(/_/g, ' ')}: ${formatValue(v, depth + 1)}`).join(', ')
      }
    }

    return '—'
  }

  return String(value)
}

export default function PillarCard({ pillar_key, pillar }: PillarCardProps) {
  const [expanded, setExpanded] = useState(false)
  const meta = PILLAR_META[pillar_key]
  const rawSummary = pillar.summary || {}

  // Built Beauty: the useful metrics live under details.architectural_analysis.metrics.
  // Some summary fields are placeholders (often zeros), so override them when available.
  const builtMetrics = pillar_key === 'built_beauty' ? pillar.details?.architectural_analysis?.metrics : null
  const summary =
    pillar_key === 'built_beauty' && isRecord(builtMetrics)
      ? {
          ...rawSummary,
          height_diversity: builtMetrics.height_diversity ?? rawSummary.height_diversity,
          type_diversity: builtMetrics.type_diversity ?? rawSummary.type_diversity,
          footprint_variation: builtMetrics.footprint_variation ?? rawSummary.footprint_variation,
          built_coverage_ratio: builtMetrics.built_coverage_ratio ?? rawSummary.built_coverage_ratio,
          // Prefer the real metric from architectural_analysis.metrics.
          // (Summary values are sometimes placeholders.)
          diversity_score:
            builtMetrics.diversity_score ?? rawSummary.diversity_score ?? pillar.details?.architectural_analysis?.score,
        }
      : rawSummary

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

      <div
        style={{
          marginTop: '1rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.9rem 1.2rem',
          alignItems: 'baseline',
        }}
      >
        <div style={{ minWidth: 110 }}>
          <div className="hf-label">Weight</div>
          <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)', fontSize: '1rem' }}>{pillar.weight.toFixed(1)}%</div>
        </div>
        <div style={{ minWidth: 130 }}>
          <div className="hf-label">Contribution</div>
          <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)', fontSize: '1rem' }}>{pillar.contribution.toFixed(1)}</div>
        </div>
        <div style={{ minWidth: 120 }}>
          <div className="hf-label">Confidence</div>
          <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)', fontSize: '1rem' }}>{pillar.confidence.toFixed(0)}%</div>
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

            {summary && Object.keys(summary).length > 0 ? (
              <div style={{ display: 'grid', gap: '0.75rem' }}>
                {Object.entries(summary).map(([key, value]) => {
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
                                {formatValue(subValue, 1)}
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
                        {formatValue(value)}
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
