'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ScoreResponse } from '@/types/api'
import type { PillarPriorities } from '@/components/SearchOptions'
import TotalScore from './TotalScore'
import PillarCard from './PillarCard'
import LongevityInfo from './LongevityInfo'
import { PILLAR_META, PILLAR_ORDER, LONGEVITY_COPY, type PillarKey } from '@/lib/pillars'

interface ScoreDisplayProps {
  data: ScoreResponse
  /** When provided, "Search another location" calls this instead of linking to #search */
  onSearchAnother?: () => void
  /** When true, show Save button (requires onSave). */
  isSignedIn?: boolean
  /** When true, auth is configured (show "Sign in to save" when not signed in). */
  isAuthConfigured?: boolean
  /** If set, show "Saved" and optional link to My places. */
  savedScoreId?: string | null
  /** Called when user clicks Save; receives current display score and priorities. */
  onSave?: (payload: ScoreResponse, priorities: PillarPriorities) => Promise<{ id?: string; error?: string }>
  /** Current priorities (for save payload). */
  priorities?: PillarPriorities
}

// Use shared pillar order from lib/pillars
function overallTier(score: number): { label: string; tone: string } {
  if (score >= 80) return { label: 'Excellent', tone: 'high' }
  if (score >= 60) return { label: 'Strong', tone: 'mid' }
  if (score >= 40) return { label: 'Mixed', tone: 'mid' }
  return { label: 'Challenging', tone: 'low' }
}

export default function ScoreDisplay({ data, onSearchAnother, isSignedIn, isAuthConfigured = true, savedScoreId, onSave, priorities }: ScoreDisplayProps) {
  const { location_info, total_score, livability_pillars, overall_confidence, metadata } = data
  const longevity_index = typeof data.longevity_index === 'number' ? data.longevity_index : null
  const [copied, setCopied] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Be defensive: backend deployments can lag the frontend pillar list.
  const available_pillars = PILLAR_ORDER.filter((k) => Boolean((livability_pillars as any)?.[k]))

  // Copy scores summary to clipboard
  const copyScores = async () => {
    const lines = [
      `HomeFit Livability Score: ${location_info.city}, ${location_info.state} ${location_info.zip}`,
      `Total Score: ${total_score.toFixed(1)}/100`,
      ...(typeof longevity_index === 'number' ? [`Longevity Index: ${longevity_index.toFixed(1)}/100`] : []),
      '',
      'Pillar Scores:',
      ...available_pillars.map((key) => {
        const score = Number((livability_pillars as any)?.[key]?.score ?? 0)
        return `  ${PILLAR_META[key].name}: ${score.toFixed(1)}/100`
      }),
    ]
    
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const pillar_ranked = available_pillars
    .map((key) => ({ key, score: Number((livability_pillars as any)?.[key]?.score ?? 0) }))
    .sort((a, b) => b.score - a.score)

  const top2 = pillar_ranked.slice(0, 2)
  const bottom1 = pillar_ranked[pillar_ranked.length - 1]
  const tier = overallTier(total_score)

  const schoolsDisabled =
    (livability_pillars.quality_education as any)?.data_quality?.fallback_used === true &&
    String((livability_pillars.quality_education as any)?.data_quality?.reason || '').toLowerCase().includes('disabled')

  const lowConfidencePillars = available_pillars.filter((k) => ((livability_pillars as any)?.[k]?.confidence ?? 100) < 60)

  const handleSave = async () => {
    if (!onSave || !priorities) return
    setSaveError(null)
    setSaving(true)
    try {
      const result = await onSave(data, priorities)
      if (result.error) setSaveError(result.error)
    } finally {
      setSaving(false)
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
            {onSave && priorities && (
              <>
                {isSignedIn ? (
                  savedScoreId ? (
                    <span className="hf-muted" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                      ✓ Saved
                      <Link href="/saved" className="hf-auth-link" style={{ fontSize: '0.95rem' }}>
                        My places
                      </Link>
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={handleSave}
                      disabled={saving}
                      className="hf-btn-secondary"
                      style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem' }}
                    >
                      {saving ? 'Saving…' : 'Save this place'}
                    </button>
                  )
                ) : isAuthConfigured ? (
                  <a
                    href="#"
                    onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                    className="hf-btn-secondary"
                    style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem', textDecoration: 'none', color: 'inherit' }}
                  >
                    Sign in to save this place
                  </a>
                ) : null}
                {saveError && (
                  <span className="hf-muted" style={{ fontSize: '0.9rem', color: 'var(--hf-danger)' }}>{saveError}</span>
                )}
              </>
            )}
            <button
              onClick={copyScores}
              className="hf-btn-primary"
              style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem' }}
            >
              {copied ? 'Copied!' : 'Copy scores'}
            </button>
            {onSearchAnother ? (
              <button type="button" onClick={onSearchAnother} className="hf-btn-link">
                Search another location
              </button>
            ) : (
              <a className="hf-btn-link" href="#search">
                Search another location
              </a>
            )}
          </div>
        </div>

        <div
          className="hf-grid-2"
          style={{
            marginTop: '2rem',
            display: 'grid',
            gridTemplateColumns: longevity_index != null ? '1fr 1fr 1.2fr' : '1fr 1.2fr',
            gap: '1.5rem',
          }}
        >
          <TotalScore score={total_score} confidence={overall_confidence} />
          {longevity_index != null && (
            <div className="hf-panel">
              <div className="hf-score-hero" style={{ padding: '0.5rem 0' }}>
                <div className="hf-score-hero__value">{longevity_index.toFixed(1)}</div>
                <div className="hf-score-hero__label" style={{ display: 'inline-flex', alignItems: 'center' }}>
                  Longevity Index (0–100)
                  <LongevityInfo />
                </div>
              </div>
              <div className="hf-muted" style={{ marginTop: '0.75rem', fontSize: '0.9rem' }}>
                {LONGEVITY_COPY.short}
              </div>
            </div>
          )}
          <div className="hf-panel">
            <div className="hf-label" style={{ marginBottom: '0.75rem' }}>
              Quick summary
            </div>

            <div style={{ fontSize: '1.05rem', color: 'var(--hf-text-primary)', fontWeight: 650, lineHeight: 1.45 }}>
              {tier.label} overall fit ({total_score.toFixed(1)}/100).
            </div>

            <div className="hf-muted" style={{ marginTop: '0.6rem', fontSize: '0.98rem' }}>
              Strongest pillars:{' '}
              {top2
                .map((p) => `${PILLAR_META[p.key].icon} ${PILLAR_META[p.key].name} (${p.score.toFixed(0)})`)
                .join(' and ')}
              . Biggest opportunity:{' '}
              {`${PILLAR_META[bottom1.key].icon} ${PILLAR_META[bottom1.key].name} (${bottom1.score.toFixed(0)})`}.
            </div>

            <div style={{ marginTop: '1rem' }}>
              <div className="hf-label" style={{ marginBottom: '0.5rem' }}>
                How to read this
              </div>
              <ul className="hf-muted" style={{ margin: 0, paddingLeft: '1.1rem', display: 'grid', gap: '0.4rem', fontSize: '0.95rem' }}>
                <li>Pillar scores are 0–100; your total is a weighted blend based on priorities.</li>
                <li>Higher-priority pillars contribute more to the total score.</li>
                {schoolsDisabled ? <li>Schools scoring is currently disabled (premium-gated), so “Schools” may be 0.</li> : null}
                {lowConfidencePillars.length ? (
                  <li>
                    Lower-confidence data in:{' '}
                    {lowConfidencePillars
                      .slice(0, 3)
                      .map((k) => PILLAR_META[k].name)
                      .join(', ')}
                    {lowConfidencePillars.length > 3 ? '…' : ''}.
                  </li>
                ) : null}
              </ul>
            </div>

            <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--hf-border)' }}>
              <div className="hf-label" style={{ marginBottom: '0.5rem' }}>
                Data notes
              </div>
              <div className="hf-muted" style={{ fontSize: '0.92rem' }}>
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
          {available_pillars.map((key) => (
            <PillarCard key={key} pillar_key={key} pillar={(livability_pillars as any)[key]} />
          ))}
        </div>
      </div>
    </div>
  )
}
