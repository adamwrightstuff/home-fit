'use client'

import { useState } from 'react'
import { LivabilityPillar } from '@/types/api'
import {
  PILLAR_META,
  getScoreBandLabel,
  getScoreBandColor,
  getScoreBandBackground,
  getPillarFailureType,
  PILLAR_LONG_DESCRIPTIONS,
  isLongevityPillar,
  LONGEVITY_COPY,
  type PillarKey,
} from '@/lib/pillars'

interface PillarCardProps {
  pillar_key: PillarKey
  pillar: LivabilityPillar
  /** When provided, Rerun button is shown for fallback/failed pillars. */
  onRerun?: (pillarKey: PillarKey) => void
  /** When true, Rerun is disabled (e.g. full run or another rerun in progress). */
  rerunDisabled?: boolean
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

export default function PillarCard({ pillar_key, pillar, onRerun, rerunDisabled }: PillarCardProps) {
  const [expanded, setExpanded] = useState(false)
  const meta = PILLAR_META[pillar_key]
  const rawSummary = pillar.summary || {}
  const failureType = getPillarFailureType(pillar)
  const showRerun = (failureType === 'fallback' || failureType === 'execution_error') && onRerun
  const isFailed = failureType === 'execution_error'
  const isFallback = failureType === 'fallback'
  const isIncomplete = failureType === 'incomplete'

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
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center', minWidth: 0 }}>
          <div style={{ fontSize: '1.6rem' }}>{meta.icon}</div>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--hf-text-primary)' }}>{meta.name}</span>
              {isLongevityPillar(pillar_key) && (
                <span
                  className="hf-muted"
                  title={LONGEVITY_COPY.tooltip}
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: 'var(--hf-bg-subtle)',
                    border: '1px solid var(--hf-border)',
                  }}
                >
                  Longevity
                </span>
              )}
              {isIncomplete && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: '#C8B84A',
                    color: 'rgba(0,0,0,0.75)',
                    border: '1px solid #A89A3A',
                  }}
                  title="Score is based on incomplete data for this location and may not be fully accurate."
                  aria-describedby={`pillar-${pillar_key}-incomplete-desc`}
                >
                  Limited data
                  <span id={`pillar-${pillar_key}-incomplete-desc`} style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                    Score is based on incomplete data for this location and may not be fully accurate.
                  </span>
                </span>
              )}
              {isFallback && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: '#C8B84A',
                    color: 'rgba(0,0,0,0.75)',
                    border: '1px solid #A89A3A',
                  }}
                  title="Real data wasn't available — this score is estimated and may not reflect this location accurately."
                  aria-describedby={`pillar-${pillar_key}-fallback-desc`}
                >
                  Estimated score
                  <span id={`pillar-${pillar_key}-fallback-desc`} style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                    Real data wasn&apos;t available — this score is estimated and may not reflect this location accurately.
                  </span>
                </span>
              )}
              {isFailed && (
                <span
                  className="hf-muted"
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: 'var(--hf-bg-subtle)',
                    border: '1px solid var(--hf-border)',
                  }}
                  title="We weren't able to retrieve data for this pillar."
                  aria-describedby={`pillar-${pillar_key}-failed-desc`}
                >
                  Data unavailable
                  <span id={`pillar-${pillar_key}-failed-desc`} style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                    We weren&apos;t able to retrieve data for this pillar.
                  </span>
                </span>
              )}
              {showRerun && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    onRerun?.(pillar_key)
                  }}
                  disabled={rerunDisabled}
                  aria-label="Rerun this pillar"
                  className="hf-btn-primary"
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    padding: '0.35rem 0.6rem',
                    minHeight: 44,
                    minWidth: 44,
                    borderRadius: 6,
                    cursor: rerunDisabled ? 'not-allowed' : 'pointer',
                    opacity: rerunDisabled ? 0.6 : 1,
                  }}
                >
                  Rerun
                </button>
              )}
            </div>
            <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
              {meta.description}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          {/* Single score badge: number + band label (or ? for failed) */}
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'baseline',
              gap: '0.35rem',
              fontWeight: 800,
              fontSize: '1.1rem',
              padding: '0.35rem 0.6rem',
              borderRadius: 8,
              background: isFailed ? 'var(--hf-bg-subtle)' : getScoreBandBackground(pillar.score),
              border: `1px solid ${isFailed ? 'var(--hf-border)' : getScoreBandColor(pillar.score)}`,
              color: isFailed ? 'var(--hf-text-secondary)' : getScoreBandColor(pillar.score),
            }}
          >
            {isFailed ? (
              '?'
            ) : (
              <>
                {isFallback && <span style={{ opacity: 0.9 }}>~</span>}
                <span style={{ color: isFailed ? undefined : 'var(--hf-text-primary)' }}>{pillar.score.toFixed(0)}</span>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, opacity: 0.95 }}>· {getScoreBandLabel(pillar.score)}</span>
              </>
            )}
          </span>
        </div>
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
          {PILLAR_LONG_DESCRIPTIONS[pillar_key] ? (
            <div className="hf-muted" style={{ fontSize: '0.95rem', marginBottom: '1rem', lineHeight: 1.5 }}>
              {PILLAR_LONG_DESCRIPTIONS[pillar_key]}
            </div>
          ) : null}
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
