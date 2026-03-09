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
  /** When provided, show "Rescore this pillar" in expanded details (below data breakdown). */
  onRescorePillar?: (pillarKey: PillarKey) => void
  /** When true, rescore link shows "Rescoring…" and is disabled. */
  rescoring?: boolean
  /** Current importance for this pillar (for inline weight editing on Results). */
  importanceLevel?: 'None' | 'Low' | 'Medium' | 'High'
  /** When provided, show None/Low/Medium/High toggle and call with new level (client-side reweight). */
  onImportanceChange?: (level: 'None' | 'Low' | 'Medium' | 'High') => void
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

export default function PillarCard({ pillar_key, pillar, onRerun, rerunDisabled, onRescorePillar, rescoring, importanceLevel, onImportanceChange }: PillarCardProps) {
  const [expanded, setExpanded] = useState(false)
  const meta = PILLAR_META[pillar_key]
  const isNone = importanceLevel === 'None'
  const mutedStyle = isNone ? { color: 'var(--hf-text-secondary)', opacity: 0.85 } : undefined
  const rawSummary = pillar.summary || {}
  // Backend may send details in summary and/or breakdown; use whichever has keys so we show something.
  const rawBreakdown = pillar.breakdown || {}
  const hasSummary = isRecord(rawSummary) && Object.keys(rawSummary).length > 0
  const hasBreakdown = isRecord(rawBreakdown) && Object.keys(rawBreakdown).length > 0
  const detailsSource = hasSummary ? rawSummary : hasBreakdown ? rawBreakdown : null
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
      : detailsSource ?? {}

  return (
    <div
      className="hf-card-sm"
      style={{ cursor: 'default' }}
    >
      {/* Top row: left = icon + name + tags; right = score + quality label */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'flex-start', minWidth: 0, flex: '1 1 0' }}>
          <div style={{ fontSize: '1.6rem', flexShrink: 0 }}>{meta.icon}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--hf-text-primary)' }}>{meta.name}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
              {isLongevityPillar(pillar_key) && (
                <span
                  className="hf-muted"
                  title={LONGEVITY_COPY.tooltip}
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: 'rgba(45, 106, 79, 0.12)',
                    color: 'var(--hf-homefit-green)',
                    border: '1px solid rgba(45, 106, 79, 0.3)',
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
            <div className="hf-muted" style={{ fontSize: '0.95rem', marginTop: '0.5rem', lineHeight: 1.4 }}>
              {meta.description}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', flexShrink: 0 }}>
          <span
            style={{
              display: 'inline-flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              fontWeight: 800,
              fontSize: '1.75rem',
              lineHeight: 1.2,
              color: isFailed ? 'var(--hf-text-secondary)' : getScoreBandColor(pillar.score),
              ...(isNone ? { color: 'var(--hf-text-secondary)', opacity: 0.85 } : {}),
            }}
          >
            {isFailed ? '?' : <>{isFallback && <span style={{ opacity: 0.9 }}>~</span>}{pillar.score.toFixed(0)}</>}
          </span>
          {!isFailed && (
            <span
              style={{
                fontSize: '0.8rem',
                fontWeight: 600,
                marginTop: '0.2rem',
                color: getScoreBandColor(pillar.score),
                ...(isNone ? { color: 'var(--hf-text-secondary)', opacity: 0.85 } : {}),
              }}
            >
              {getScoreBandLabel(pillar.score)}
            </span>
          )}
        </div>
      </div>

      {/* Importance: pill-style Low / Medium / High (and None when editable) */}
      {onImportanceChange != null ? (
        <div style={{ marginTop: '1rem' }}>
          <div className="hf-label" style={{ marginBottom: '0.5rem' }}>Importance</div>
          <div style={{ display: 'inline-flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {(['None', 'Low', 'Medium', 'High'] as const).map((level) => (
              <button
                key={level}
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onImportanceChange(level)
                }}
                style={{
                  padding: '0.4rem 0.75rem',
                  minHeight: 40,
                  fontSize: '0.9rem',
                  fontWeight: importanceLevel === level ? 700 : 500,
                  borderRadius: 999,
                  border: `1px solid ${importanceLevel === level ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                  background: importanceLevel === level ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                  color: importanceLevel === level ? 'white' : 'var(--hf-text-secondary)',
                  cursor: 'pointer',
                }}
              >
                {level}
              </button>
            ))}
          </div>
          {/* Status bar: green fill representing weight (or score) */}
          <div
            style={{
              marginTop: '0.6rem',
              height: 6,
              borderRadius: 999,
              background: 'var(--hf-border)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${Math.min(100, (pillar.weight ?? 0))}%`,
                borderRadius: 999,
                background: 'var(--hf-homefit-green)',
                transition: 'width 0.25s ease',
              }}
            />
          </div>
        </div>
      ) : null}

      {/* Metrics: Weight, Contribution, Confidence */}
      <div
        style={{
          marginTop: '1rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '0.75rem 1rem',
          alignItems: 'baseline',
        }}
      >
        <div>
          <div className="hf-label" style={{ fontSize: '0.8rem', marginBottom: '0.2rem' }}>Weight</div>
          <div style={{ fontWeight: 800, color: isNone ? 'var(--hf-text-secondary)' : 'var(--hf-text-primary)', fontSize: '1rem', opacity: isNone ? 0.85 : 1 }}>
            {Number(pillar.weight).toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="hf-label" style={{ fontSize: '0.8rem', marginBottom: '0.2rem' }}>Contribution</div>
          <div style={{ fontWeight: 800, color: isNone ? 'var(--hf-text-secondary)' : 'var(--hf-text-primary)', fontSize: '1rem', opacity: isNone ? 0.85 : 1 }}>
            {pillar.contribution.toFixed(1)}
          </div>
        </div>
        <div>
          <div className="hf-label" style={{ fontSize: '0.8rem', marginBottom: '0.2rem' }}>Confidence</div>
          <div style={{ fontWeight: 800, color: isNone ? 'var(--hf-text-secondary)' : 'var(--hf-text-primary)', fontSize: '1rem', opacity: isNone ? 0.85 : 1 }}>
            {pillar.confidence.toFixed(0)}%
          </div>
        </div>
      </div>

      <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          className="hf-btn-link"
          onClick={() => setExpanded((v) => !v)}
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

          {onRescorePillar ? (
            <div style={{ marginTop: '1.25rem' }}>
              {pillar.confidence < 50 && (
                <div
                  role="status"
                  style={{
                    fontSize: '0.9rem',
                    padding: '0.6rem 0.75rem',
                    marginBottom: '0.75rem',
                    borderRadius: 8,
                    background: 'rgba(200, 184, 74, 0.15)',
                    border: '1px solid rgba(168, 154, 58, 0.4)',
                    color: 'var(--hf-text-primary)',
                  }}
                >
                  Low confidence data — rescore for better results
                </div>
              )}
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  onRescorePillar(pillar_key)
                }}
                disabled={rescoring}
                className="hf-btn-link"
                style={{
                  fontSize: pillar.confidence >= 50 ? '0.85rem' : '0.95rem',
                  padding: pillar.confidence >= 50 ? '0.25rem 0' : '0.5rem 0',
                  opacity: rescoring ? 0.7 : 1,
                  ...(pillar.confidence >= 50 ? { color: 'var(--hf-text-secondary)' } : {}),
                }}
              >
                {rescoring ? 'Rescoring…' : 'Rescore this pillar'}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
