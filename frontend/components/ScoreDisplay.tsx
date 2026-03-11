'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { ScoreResponse } from '@/types/api'
import type { PillarPriorities, SearchOptions } from '@/components/SearchOptions'
import TotalScore from './TotalScore'
import PillarCard from './PillarCard'
import LongevityInfo from './LongevityInfo'
import { PILLAR_META, PILLAR_ORDER, LONGEVITY_COPY, type PillarKey } from '@/lib/pillars'
import { useAuth } from '@/contexts/AuthContext'

/** Options passed to onRunPillarScore when user runs a score for a single pillar from the "+ Add" expand. */
export interface RunPillarScoreOptions {
  priorities: PillarPriorities
  job_categories?: string[]
  natural_beauty_preference?: string[] | null
  built_character_preference?: 'historic' | 'contemporary' | 'no_preference' | null
  built_density_preference?: 'spread_out_residential' | 'walkable_residential' | 'dense_urban_living' | null
  include_chains?: boolean
  enable_schools?: boolean
}

// Preference UI constants for the "+ Add" inline expand (mirrors PlaceView / SearchOptions).
const ADD_JOB_CATEGORY_OPTIONS: Array<{ key: string; label: string }> = [
  { key: 'tech_professional', label: 'Tech / Product' },
  { key: 'business_finance_law', label: 'Business / Finance / Law' },
  { key: 'healthcare_education', label: 'Healthcare / Education' },
  { key: 'skilled_trades_logistics', label: 'Skilled trades / Logistics' },
  { key: 'service_retail_hospitality', label: 'Service / Retail / Hospitality' },
  { key: 'public_sector_nonprofit', label: 'Public sector' },
  { key: 'remote_flexible', label: 'Remote / Flexible' },
]
const ADD_NATURAL_BEAUTY_CHIPS: Array<{ value: string | null; label: string }> = [
  { value: null, label: 'Any' },
  { value: 'mountains', label: 'Mountains' },
  { value: 'ocean', label: 'Ocean' },
  { value: 'lakes_rivers', label: 'Lakes & rivers' },
  { value: 'canopy', label: 'Greenery' },
]
const ADD_BUILT_CHARACTER_CHIPS: Array<{ value: 'historic' | 'contemporary' | 'no_preference'; label: string }> = [
  { value: 'historic', label: 'Historic' },
  { value: 'contemporary', label: 'Contemporary' },
  { value: 'no_preference', label: 'No preference' },
]
const ADD_BUILT_DENSITY_CHIPS: Array<{ value: 'spread_out_residential' | 'walkable_residential' | 'dense_urban_living'; label: string }> = [
  { value: 'spread_out_residential', label: 'Spread out' },
  { value: 'walkable_residential', label: 'Walkable' },
  { value: 'dense_urban_living', label: 'Downtown' },
]

interface ScoreDisplayProps {
  data: ScoreResponse
  /** When true, show progressive/skeleton state (used while async job is running). */
  loading?: boolean
  /** When loading, which pillar cards should render as loading. */
  pillarLoadingKeys?: Set<PillarKey>
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
  /** When set, show this as the main summary (e.g. from Configuration page) instead of the built-in quick summary. */
  placeSummary?: string | null
  /** Optional search options to prefill preference inputs when expanding "+ Add" (e.g. job categories, natural beauty). */
  searchOptions?: SearchOptions | null
  /** Optional: update searchOptions from within results UI (e.g. Amenities include_chains toggle). */
  onSearchOptionsChange?: (options: SearchOptions) => void
  /** When provided, "+ Add" expands inline with importance + preferences and "Run Score"; called to run single-pillar score. */
  onRunPillarScore?: (pillarKey: PillarKey, options: RunPillarScoreOptions) => Promise<void>
  /** When provided, pillar cards show "Rescore this pillar" in expanded details; called to run single-pillar score with current state. */
  onRescorePillar?: (pillarKey: PillarKey) => void | Promise<void>
  /** When set, the matching pillar card shows rescore link as "Rescoring…" and disables it. */
  rescoringPillarKey?: PillarKey | null
}

// Use shared pillar order from lib/pillars
function overallTier(score: number): { label: string; tone: string } {
  if (score >= 80) return { label: 'Excellent', tone: 'high' }
  if (score >= 60) return { label: 'Strong', tone: 'mid' }
  if (score >= 40) return { label: 'Mixed', tone: 'mid' }
  return { label: 'Challenging', tone: 'low' }
}

export default function ScoreDisplay({
  data,
  loading,
  pillarLoadingKeys,
  onSearchAnother,
  isSignedIn,
  isAuthConfigured = true,
  savedScoreId,
  onSave,
  priorities,
  onReconfigure,
  onPrioritiesChange,
  placeSummary,
  searchOptions,
  onSearchOptionsChange,
  onRunPillarScore,
  onRescorePillar,
  rescoringPillarKey,
}: ScoreDisplayProps) {
  const { openAuthModal } = useAuth()
  const { location_info, total_score, livability_pillars, overall_confidence, metadata } = data
  const isLoading = Boolean(loading)
  const longevity_index = typeof data.longevity_index === 'number' ? data.longevity_index : null
  const [copied, setCopied] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Inline expand for "+ Add" pillar: which pillar is expanded and its local importance + preferences.
  const [expandedAddPillar, setExpandedAddPillar] = useState<PillarKey | null>(null)
  const [addPillarImportance, setAddPillarImportance] = useState<'Low' | 'Medium' | 'High'>('Medium')
  const [addPillarJobCategories, setAddPillarJobCategories] = useState<string[]>([])
  const [addPillarNaturalBeauty, setAddPillarNaturalBeauty] = useState<string[] | null>(null)
  const [addPillarBuiltCharacter, setAddPillarBuiltCharacter] = useState<'historic' | 'contemporary' | 'no_preference' | null>(null)
  const [addPillarBuiltDensity, setAddPillarBuiltDensity] = useState<'spread_out_residential' | 'walkable_residential' | 'dense_urban_living' | null>(null)
  const [runPillarLoading, setRunPillarLoading] = useState(false)
  const [runPillarError, setRunPillarError] = useState<string | null>(null)

  // Be defensive: backend deployments can lag the frontend pillar list.
  const available_pillars = PILLAR_ORDER.filter((k) => Boolean((livability_pillars as any)?.[k]))
  // Main list: all pillars that have a score (fixed order). When priority is None, show muted on card.
  const included_pillars = PILLAR_ORDER.filter((k) => available_pillars.includes(k))
  // Not included: only pillars with no score in the payload (compact "+ Add" section).
  const not_included_pillars = PILLAR_ORDER.filter((k) => !available_pillars.includes(k))

  // When the expanded pillar gets a score (merged by parent), it leaves not_included_pillars; collapse expand.
  useEffect(() => {
    if (expandedAddPillar && !not_included_pillars.includes(expandedAddPillar)) {
      setExpandedAddPillar(null)
      setRunPillarError(null)
    }
  }, [expandedAddPillar, not_included_pillars])

  // Copy scores summary to clipboard
  const copyScores = async () => {
    if (isLoading) return
    const lines = [
      `HomeFit Livability Score: ${locationDisplayName}`,
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

  /** Prefer original search input; fall back to city, state zip for display. */
  const locationDisplayName =
    (typeof data.input === 'string' && data.input.trim()) || [location_info.city, location_info.state, location_info.zip].filter(Boolean).join(', ') || 'Unknown location'

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

  const handleAddPillarClick = (key: PillarKey) => {
    if (onRunPillarScore) {
      setExpandedAddPillar(key)
      setAddPillarImportance('Medium')
      setAddPillarJobCategories(Array.isArray(searchOptions?.job_categories) ? [...searchOptions.job_categories] : [])
      const nb = searchOptions?.natural_beauty_preference
      setAddPillarNaturalBeauty(nb && nb.length > 0 ? [...nb] : null)
      setAddPillarBuiltCharacter(searchOptions?.built_character_preference ?? null)
      setAddPillarBuiltDensity(searchOptions?.built_density_preference ?? null)
      setRunPillarError(null)
    } else if (onPrioritiesChange && priorities) {
      const next = { ...priorities } as PillarPriorities
      next[key as keyof PillarPriorities] = 'Medium'
      onPrioritiesChange(next)
    }
  }

  const handleRunPillarScore = async () => {
    if (!expandedAddPillar || !onRunPillarScore || !priorities) return
    setRunPillarError(null)
    setRunPillarLoading(true)
    try {
      const nextPriorities = { ...priorities } as PillarPriorities
      nextPriorities[expandedAddPillar as keyof PillarPriorities] = addPillarImportance
      await onRunPillarScore(expandedAddPillar, {
        priorities: nextPriorities,
        job_categories: addPillarJobCategories.length > 0 ? addPillarJobCategories : undefined,
        natural_beauty_preference: addPillarNaturalBeauty && addPillarNaturalBeauty.length > 0 ? addPillarNaturalBeauty : null,
        built_character_preference: addPillarBuiltCharacter,
        built_density_preference: addPillarBuiltDensity,
        include_chains: searchOptions?.include_chains,
        enable_schools: searchOptions?.enable_schools,
      })
    } catch (e) {
      setRunPillarError(e instanceof Error ? e.message : 'Failed to run score')
    } finally {
      setRunPillarLoading(false)
    }
  }

  return (
    <div style={{ marginTop: '1.5rem', display: 'grid', gap: '1.5rem' }}>
      <div className="hf-card">
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
              {locationDisplayName}
            </div>
            {(typeof data.input === 'string' && data.input.trim()) && (
              <div className="hf-muted" style={{ marginTop: '0.5rem', fontSize: '0.95rem' }}>
                Location: {location_info.city}, {location_info.state} {location_info.zip}
              </div>
            )}
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
              disabled={isLoading}
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
          <TotalScore score={total_score} confidence={overall_confidence} loading={isLoading} />
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
              {placeSummary != null && placeSummary !== '' ? 'Summary' : 'Quick summary'}
            </div>

            {isLoading ? (
              <div className="hf-muted" style={{ fontSize: '1.05rem', lineHeight: 1.45 }}>
                Calculating your full results…
              </div>
            ) : placeSummary != null && placeSummary !== '' ? (
              <p
                style={{
                  margin: 0,
                  fontSize: '1.05rem',
                  lineHeight: 1.45,
                  color: 'var(--hf-text-primary)',
                  fontWeight: 500,
                }}
              >
                {placeSummary}
              </p>
            ) : (
              <>
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
              </>
            )}

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
          YOUR SCORED PILLARS
        </div>
        <div className="hf-pillar-cards-grid">
          {included_pillars.map((key) => {
            const pillar = (livability_pillars as any)[key]
            const importanceLevel = priorities?.[key as keyof typeof priorities]
            const level = importanceLevel === 'None' || importanceLevel === 'Low' || importanceLevel === 'Medium' || importanceLevel === 'High' ? importanceLevel : 'Medium'
            return (
              <PillarCard
                key={key}
                pillar_key={key}
                pillar={pillar}
                loading={Boolean(isLoading && pillarLoadingKeys?.has(key))}
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
                onRescorePillar={onRescorePillar}
                rescoring={rescoringPillarKey === key}
                includeChainsValue={key === 'neighborhood_amenities' ? Boolean(searchOptions?.include_chains) : undefined}
                onIncludeChainsChange={
                  key === 'neighborhood_amenities' && onSearchOptionsChange && searchOptions
                    ? (next) => {
                        onSearchOptionsChange({ ...searchOptions, include_chains: next })
                        // Immediately rescore just this pillar when available.
                        if (onRescorePillar) onRescorePillar('neighborhood_amenities')
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
                  const isExpanded = expandedAddPillar === key
                  const canRunScore = Boolean(onRunPillarScore)
                  return (
                    <div
                      key={key}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.75rem',
                        padding: isExpanded ? '0.75rem' : 0,
                        borderRadius: 8,
                        background: isExpanded ? 'var(--hf-bg-subtle)' : undefined,
                        border: isExpanded ? '1px solid var(--hf-border)' : undefined,
                      }}
                    >
                      <div
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
                        {(onPrioritiesChange || onRunPillarScore) && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault()
                              if (isExpanded) {
                                setExpandedAddPillar(null)
                                setRunPillarError(null)
                              } else {
                                handleAddPillarClick(key)
                              }
                            }}
                            className="hf-btn-link"
                            style={{ fontSize: '0.9rem', padding: '0.35rem 0.65rem', minHeight: 36 }}
                          >
                            {isExpanded ? 'Cancel' : '+ Add'}
                          </button>
                        )}
                      </div>

                      {isExpanded && (
                        <>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span className="hf-muted" style={{ fontSize: '0.85rem' }}>Importance:</span>
                            {(['Low', 'Medium', 'High'] as const).map((level) => (
                              <button
                                key={level}
                                type="button"
                                onClick={() => setAddPillarImportance(level)}
                                style={{
                                  padding: '0.35rem 0.65rem',
                                  borderRadius: 8,
                                  fontSize: '0.85rem',
                                  fontWeight: addPillarImportance === level ? 700 : 400,
                                  background: addPillarImportance === level ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                                  color: addPillarImportance === level ? 'white' : 'var(--hf-text-secondary)',
                                  border: `1px solid ${addPillarImportance === level ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                                  cursor: 'pointer',
                                }}
                              >
                                {level}
                              </button>
                            ))}
                          </div>

                          {key === 'economic_security' && (
                            <div>
                              <div className="hf-muted" style={{ fontSize: '0.85rem', marginBottom: '0.35rem' }}>Job categories (optional)</div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                                {ADD_JOB_CATEGORY_OPTIONS.map((opt) => {
                                  const checked = addPillarJobCategories.includes(opt.key)
                                  return (
                                    <label key={opt.key} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) => {
                                          if (e.target.checked) setAddPillarJobCategories((prev) => [...prev, opt.key])
                                          else setAddPillarJobCategories((prev) => prev.filter((k) => k !== opt.key))
                                        }}
                                      />
                                      <span>{opt.label}</span>
                                    </label>
                                  )
                                })}
                              </div>
                            </div>
                          )}

                          {key === 'natural_beauty' && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                              <span className="hf-muted" style={{ fontSize: '0.85rem' }}>Scenery (up to 2):</span>
                              {ADD_NATURAL_BEAUTY_CHIPS.map(({ value, label }) => {
                                const isAny = value === null
                                const hasAny = !addPillarNaturalBeauty?.length || (addPillarNaturalBeauty.length === 1 && addPillarNaturalBeauty[0] === 'no_preference')
                                const selected = isAny ? hasAny : (addPillarNaturalBeauty?.includes(value as string) ?? false)
                                const atMax = !isAny && (addPillarNaturalBeauty?.length ?? 0) >= 2 && !addPillarNaturalBeauty?.includes(value as string)
                                return (
                                  <button
                                    key={label}
                                    type="button"
                                    onClick={() => {
                                      if (isAny) {
                                        setAddPillarNaturalBeauty(null)
                                        return
                                      }
                                      const current = (addPillarNaturalBeauty ?? []).filter((v) => v !== 'no_preference')
                                      if (current.includes(value as string)) {
                                        const next = current.filter((v) => v !== value)
                                        setAddPillarNaturalBeauty(next.length ? next : null)
                                      } else if (current.length >= 2) {
                                        setAddPillarNaturalBeauty([current[1], value as string])
                                      } else {
                                        setAddPillarNaturalBeauty([...current, value as string])
                                      }
                                    }}
                                    disabled={atMax}
                                    style={{
                                      padding: '0.35rem 0.65rem',
                                      borderRadius: 8,
                                      fontSize: '0.85rem',
                                      fontWeight: selected ? 600 : 400,
                                      background: selected ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                                      color: selected ? 'white' : atMax ? 'var(--hf-text-tertiary)' : 'var(--hf-text-secondary)',
                                      border: `1px solid ${selected ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                                      cursor: atMax ? 'not-allowed' : 'pointer',
                                      opacity: atMax ? 0.7 : 1,
                                    }}
                                  >
                                    {label}
                                  </button>
                                )
                              })}
                            </div>
                          )}

                          {key === 'built_beauty' && (
                            <>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <span className="hf-muted" style={{ fontSize: '0.85rem' }}>Character:</span>
                                {ADD_BUILT_CHARACTER_CHIPS.map(({ value, label }) => (
                                  <button
                                    key={value}
                                    type="button"
                                    onClick={() => setAddPillarBuiltCharacter(addPillarBuiltCharacter === value ? null : value)}
                                    style={{
                                      padding: '0.35rem 0.65rem',
                                      borderRadius: 8,
                                      fontSize: '0.85rem',
                                      fontWeight: addPillarBuiltCharacter === value ? 600 : 400,
                                      background: addPillarBuiltCharacter === value ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                                      color: addPillarBuiltCharacter === value ? 'white' : 'var(--hf-text-secondary)',
                                      border: `1px solid ${addPillarBuiltCharacter === value ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                                      cursor: 'pointer',
                                    }}
                                  >
                                    {label}
                                  </button>
                                ))}
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <span className="hf-muted" style={{ fontSize: '0.85rem' }}>Density:</span>
                                {ADD_BUILT_DENSITY_CHIPS.map(({ value, label }) => (
                                  <button
                                    key={value}
                                    type="button"
                                    onClick={() => setAddPillarBuiltDensity(addPillarBuiltDensity === value ? null : value)}
                                    style={{
                                      padding: '0.35rem 0.65rem',
                                      borderRadius: 8,
                                      fontSize: '0.85rem',
                                      fontWeight: addPillarBuiltDensity === value ? 600 : 400,
                                      background: addPillarBuiltDensity === value ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                                      color: addPillarBuiltDensity === value ? 'white' : 'var(--hf-text-secondary)',
                                      border: `1px solid ${addPillarBuiltDensity === value ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                                      cursor: 'pointer',
                                    }}
                                  >
                                    {label}
                                  </button>
                                ))}
                              </div>
                            </>
                          )}

                          {canRunScore && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                              <button
                                type="button"
                                onClick={handleRunPillarScore}
                                disabled={runPillarLoading}
                                className="hf-btn-primary"
                                style={{ padding: '0.5rem 1rem', borderRadius: 8, fontSize: '0.9rem', minHeight: 40 }}
                              >
                                {runPillarLoading ? 'Running score…' : 'Run Score'}
                              </button>
                              {runPillarError && (
                                <span className="hf-muted" style={{ fontSize: '0.9rem', color: 'var(--hf-danger)' }}>{runPillarError}</span>
                              )}
                            </div>
                          )}
                        </>
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
