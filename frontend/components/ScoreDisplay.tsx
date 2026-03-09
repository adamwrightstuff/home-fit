'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ScoreResponse } from '@/types/api'
import type { PillarPriorities } from '@/components/SearchOptions'
import TotalScore from './TotalScore'
import PillarCard from './PillarCard'
import LongevityInfo from './LongevityInfo'
import { PILLAR_META, PILLAR_ORDER, LONGEVITY_COPY, type PillarKey } from '@/lib/pillars'
import { useAuth } from '@/contexts/AuthContext'

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
  /** When provided, show "Edit pillars" and call this to return to Configure with same place/state. */
  onReconfigure?: () => void
  /** When user changes importance on a pillar card, call with updated priorities (client-side reweight; no API). */
  onPrioritiesChange?: (priorities: PillarPriorities) => void
}

// Use shared pillar order from lib/pillars
function overallTier(score: number): { label: string; tone: string } {
  if (score >= 80) return { label: 'Excellent', tone: 'high' }
  if (score >= 60) return { label: 'Strong', tone: 'mid' }
  if (score >= 40) return { label: 'Mixed', tone: 'mid' }
  return { label: 'Challenging', tone: 'low' }
}

export default function ScoreDisplay({ data, onSearchAnother, isSignedIn, isAuthConfigured = true, savedScoreId, onSave, priorities, onReconfigure, onPrioritiesChange }: ScoreDisplayProps) {
  const { openAuthModal } = useAuth()
  const { location_info, total_score, livability_pillars, overall_confidence, metadata } = data
  const longevity_index = typeof data.longevity_index === 'number' ? data.longevity_index : null
  const [copied, setCopied] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Be defensive: backend deployments can lag the frontend pillar list.
  const available_pillars = PILLAR_ORDER.filter((k) => Boolean((livability_pillars as any)?.[k]))
  // Main list: all pillars that have a score (fixed order). When priority is None, show muted on card.
  const included_pillars = PILLAR_ORDER.filter((k) => available_pillars.includes(k))
  // Not included: only pillars with no score in the payload (compact "+ Add" section).
  const not_included_pillars = PILLAR_ORDER.filter((k) => !available_pillars.includes(k))

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
      <div className="hf-card hf-score-summary-sticky">
        {/* Prominent Save row: first thing under the location so it’s impossible to miss */}
        {onSave && priorities && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '1rem 1.25rem',
              marginBottom: '0.5rem',
              background: 'var(--hf-bg-subtle)',
              borderRadius: 12,
              border: '1px solid var(--hf-border)',
            }}
          >
            {isSignedIn ? (
              savedScoreId ? (
                <span className="hf-muted" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '1rem' }}>
                  ✓ Saved to My places
                  <Link href="/saved" className="hf-auth-link" style={{ fontWeight: 600 }}>
                    View saved places →
                  </Link>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="hf-btn-primary"
                  style={{ padding: '0.85rem 1.5rem', borderRadius: 12, fontSize: '1rem', fontWeight: 600, minHeight: 44 }}
                >
                  {saving ? 'Saving…' : 'Save this place'}
                </button>
              )
            ) : isAuthConfigured ? (
              <button
                type="button"
                onClick={() => openAuthModal('signin')}
                className="hf-btn-primary"
                style={{ padding: '0.85rem 1.5rem', borderRadius: 12, fontSize: '1rem', fontWeight: 600 }}
              >
                Sign in to save this place
              </button>
            ) : null}
            {saveError && (
              <span className="hf-muted" style={{ fontSize: '0.9rem', color: 'var(--hf-danger)' }}>{saveError}</span>
            )}
          </div>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
          <div style={{ minWidth: 0, flex: '1 1 260px' }}>
            <div className="hf-label" style={{ marginBottom: '0.25rem' }}>
              Score summary for
            </div>
            <div style={{ fontSize: 'clamp(1.35rem, 4vw, 1.8rem)', fontWeight: 800, color: 'var(--hf-text-primary)' }}>
              {location_info.city}, {location_info.state} {location_info.zip}
            </div>
            <div className="hf-muted" style={{ marginTop: '0.5rem', fontSize: '0.95rem' }}>
              Input: {data.input}
            </div>
            <div className="hf-muted" style={{ marginTop: '0.25rem', fontSize: '0.9rem' }}>
              Coordinates: {data.coordinates.lat.toFixed(6)}, {data.coordinates.lon.toFixed(6)}
            </div>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
            {onReconfigure && (
              <button type="button" onClick={onReconfigure} className="hf-btn-link" style={{ fontSize: '0.95rem' }}>
                Edit pillars
              </button>
            )}
            <button
              onClick={copyScores}
              className="hf-btn-secondary"
              style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem', minHeight: 44 }}
            >
              {copied ? 'Copied!' : 'Copy scores'}
            </button>
            {onSearchAnother ? (
              <button type="button" onClick={onSearchAnother} className="hf-btn-link" style={{ fontSize: '0.95rem' }}>
                Search another location
              </button>
            ) : (
              <a className="hf-btn-link" href="#search" style={{ fontSize: '0.95rem' }}>
                Search another location
              </a>
            )}
          </div>
        </div>

        <div
          className={`hf-score-summary-grid ${longevity_index != null ? 'hf-score-summary-grid-3' : ''}`}
          style={{ marginTop: '2rem' }}
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
              {top2.length >= 2
                ? top2
                    .map((p) => `${PILLAR_META[p.key].icon} ${PILLAR_META[p.key].name} (${p.score.toFixed(0)})`)
                    .join(' and ')
                : top2.map((p) => `${PILLAR_META[p.key].icon} ${PILLAR_META[p.key].name} (${p.score.toFixed(0)})`).join(' and ')}
              . Biggest opportunity:{' '}
              {bottom1
                ? `${PILLAR_META[bottom1.key].icon} ${PILLAR_META[bottom1.key].name} (${bottom1.score.toFixed(0)})`
                : '—'}
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
          {included_pillars.map((key) => {
            const pillar = (livability_pillars as any)[key]
            const importanceLevel = priorities?.[key as keyof typeof priorities]
            const level = importanceLevel === 'None' || importanceLevel === 'Low' || importanceLevel === 'Medium' || importanceLevel === 'High' ? importanceLevel : 'Medium'
            return (
              <PillarCard
                key={key}
                pillar_key={key}
                pillar={pillar}
                importanceLevel={level}
                onImportanceChange={
                  onPrioritiesChange
                    ? (newLevel) => {
                        const next = { ...priorities } as PillarPriorities
                        next[key as keyof PillarPriorities] = newLevel
                        onPrioritiesChange(next)
                      }
                    : undefined
                }
              />
            )
          })}
        </div>

        {not_included_pillars.length > 0 && (
          <div style={{ marginTop: '2rem' }}>
            <div className="hf-label" style={{ marginBottom: '0.75rem', color: 'var(--hf-text-secondary)', fontSize: '0.95rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Not included in your score
            </div>
            <div className="hf-panel" style={{ padding: '1rem 1.25rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {not_included_pillars.map((key) => {
                  const pillar = (livability_pillars as any)[key]
                  const hasScore = pillar && typeof pillar.score === 'number'
                  const score = hasScore ? Number(pillar.score) : null
                  return (
                    <div
                      key={key}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '0.75rem',
                        flexWrap: 'wrap',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                        <span style={{ fontSize: '1.25rem' }}>{PILLAR_META[key].icon}</span>
                        <span style={{ fontWeight: 700, color: 'var(--hf-text-secondary)', fontSize: '0.95rem' }}>
                          {PILLAR_META[key].name}
                        </span>
                        {score != null && (
                          <span
                            className="hf-muted"
                            style={{
                              fontSize: '0.85rem',
                              fontWeight: 700,
                              padding: '0.2rem 0.5rem',
                              borderRadius: 6,
                              background: 'var(--hf-bg-subtle)',
                              border: '1px solid var(--hf-border)',
                              opacity: 0.85,
                            }}
                          >
                            {score.toFixed(0)}
                          </span>
                        )}
                      </div>
                      {onPrioritiesChange && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault()
                            const next = { ...priorities } as PillarPriorities
                            next[key as keyof PillarPriorities] = 'Medium'
                            onPrioritiesChange(next)
                          }}
                          className="hf-btn-link"
                          style={{ fontSize: '0.9rem', padding: '0.35rem 0.65rem', minHeight: 36 }}
                        >
                          + Add
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
