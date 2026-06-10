'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import type { ScoreResponse } from '@/types/api'
import type { SavedScoreRow } from '@/lib/savedScores'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { longevityIndexFromLivabilityPillars, HOMEFIT_COPY } from '@/lib/pillars'
import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'
import type { PillarPriorities } from '@/components/SearchOptions'
import ScoreDisplay from '@/components/ScoreDisplay'
import InteractiveMap from '@/components/InteractiveMap'
import HomeFitInfo from '@/components/HomeFitInfo'
import LongevityInfo from '@/components/LongevityInfo'
import StatusSignalInfo from '@/components/StatusSignalInfo'
import HappinessInfo from '@/components/HappinessInfo'

function prioritiesFromRow(row: SavedScoreRow): PillarPriorities {
  const p = row.priorities as Record<string, string> | null | undefined
  if (!p || typeof p !== 'object') return { ...DEFAULT_PRIORITIES }
  const levels = ['None', 'Low', 'Medium', 'High'] as const
  const out: Record<string, (typeof levels)[number]> = { ...DEFAULT_PRIORITIES }
  for (const k of Object.keys(out)) {
    const v = String(p[k] ?? '').trim()
    if (levels.includes(v as (typeof levels)[number])) {
      out[k] = v as (typeof levels)[number]
    }
  }
  return out as unknown as PillarPriorities
}

export default function PublicPlacePage() {
  const params = useParams()
  const id = typeof params.id === 'string' ? params.id : null

  const [row, setRow] = useState<SavedScoreRow | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [priorities, setPriorities] = useState<PillarPriorities>(DEFAULT_PRIORITIES)

  useEffect(() => {
    if (!id) { setLoading(false); return }
    fetch(`/api/p/${id}`)
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).error ?? 'Not found')
        return res.json() as Promise<SavedScoreRow>
      })
      .then((r) => {
        setRow(r)
        setPriorities(prioritiesFromRow(r))
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id])

  const rawPayload = row?.score_payload as ScoreResponse | undefined

  const displayData = useMemo(() => {
    if (!rawPayload) return null
    const rew = reweightScoreResponseFromPriorities(rawPayload, priorities)
    const li = longevityIndexFromLivabilityPillars(
      rew.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
    )
    return li != null ? { ...rew, longevity_index: li } : rew
  }, [rawPayload, priorities])

  if (loading) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <p className="tr-muted" style={{ marginTop: '3rem', textAlign: 'center' }}>Loading…</p>
        </div>
      </main>
    )
  }

  if (error || !row || !displayData) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <div style={{ marginTop: '4rem', textAlign: 'center' }}>
            <p style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--hf-text-primary)', marginBottom: '0.5rem' }}>
              This link isn't available
            </p>
            <p className="tr-muted" style={{ marginBottom: '1.5rem' }}>
              {error ?? "This place score is either private or doesn't exist."}
            </p>
            <Link href="/" className="hf-btn-secondary" style={{ padding: '0.75rem 1.5rem' }}>
              Try Trovamo
            </Link>
          </div>
        </div>
      </main>
    )
  }

  const locationLabel =
    (typeof row.input === 'string' && row.input.trim()) ||
    [row.location_info?.city, row.location_info?.state, row.location_info?.zip].filter(Boolean).join(', ') ||
    'Unknown location'

  const coordinates = rawPayload?.coordinates ?? row.coordinates
  const totalScore = displayData.total_score
  const longevityIndex = typeof displayData.longevity_index === 'number' ? displayData.longevity_index : null
  const happinessIndex = typeof displayData.happiness_index === 'number' ? displayData.happiness_index : null
  const { location_info } = displayData

  return (
    <main className="hf-page hf-page-no-hero">
      <div className="hf-container">
        {/* Trovamo branding bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.75rem 0',
            marginBottom: '0.25rem',
            borderBottom: '1px solid var(--hf-border)',
          }}
        >
          <Link
            href="/"
            style={{
              fontSize: '1rem',
              fontWeight: 800,
              color: 'var(--hf-text-primary)',
              textDecoration: 'none',
              letterSpacing: '-0.02em',
            }}
          >
            Trovamo
          </Link>
          <Link href="/" className="hf-btn-secondary" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
            Score your own →
          </Link>
        </div>

        <div className="hf-card" style={{ marginTop: '1rem', paddingBottom: '1.5rem' }}>
          {/* Header */}
          <div
            style={{
              padding: '1rem 1.25rem',
              background: 'var(--hf-bg-subtle)',
              borderRadius: 12,
              border: '1px solid var(--hf-border)',
              marginBottom: '1.25rem',
            }}
          >
            <div className="tr-label" style={{ marginBottom: '0.25rem' }}>Trovamo score for</div>
            <div style={{ fontSize: 'clamp(1.35rem, 4vw, 1.8rem)', fontWeight: 800, color: 'var(--hf-text-primary)' }}>
              {locationLabel}
            </div>
            {location_info && (
              <div className="tr-muted" style={{ marginTop: '0.4rem', fontSize: '0.9rem' }}>
                {[location_info.city, location_info.state, location_info.zip].filter(Boolean).join(', ')}
              </div>
            )}
          </div>

          {/* Map */}
          <div
            style={{
              width: '100%',
              height: '260px',
              borderRadius: 12,
              overflow: 'hidden',
              marginBottom: '1.25rem',
              background: 'var(--hf-bg-subtle)',
            }}
          >
            <InteractiveMap
              location={locationLabel}
              coordinates={coordinates}
              completed_pillars={Object.keys(displayData.livability_pillars ?? {})}
            />
          </div>

          {/* Score summary */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              padding: '1rem 0.75rem',
            }}
          >
            <div
              style={{
                fontSize: '2.5rem',
                fontWeight: 800,
                color: totalScore != null ? 'var(--c-purple-600)' : 'var(--hf-text-secondary)',
                lineHeight: 1.1,
              }}
            >
              {totalScore != null ? totalScore.toFixed(1) : '—'}
            </div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                fontSize: '0.875rem',
                fontWeight: 600,
                color: 'var(--hf-text-secondary)',
                marginTop: '0.25rem',
              }}
            >
              Trovamo Score
              <HomeFitInfo />
            </div>
            <div className="tr-muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem', textAlign: 'center', maxWidth: 320 }}>
              {HOMEFIT_COPY.subtitle}
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexWrap: 'wrap',
                gap: '1.25rem',
                marginTop: '1rem',
                fontSize: '0.8rem',
                color: 'var(--hf-text-secondary)',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <span className="tr-muted">Longevity</span>
                <span style={{ fontWeight: 600, color: longevityIndex != null ? 'var(--c-teal-600)' : 'var(--hf-text-secondary)' }}>
                  {longevityIndex != null ? longevityIndex.toFixed(1) : '—'}
                </span>
                <LongevityInfo />
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <span className="tr-muted">Archetype</span>
                <span style={{ fontWeight: 600, color: typeof displayData.status_signal === 'number' ? 'var(--c-coral-600)' : 'var(--hf-text-secondary)' }}>
                  {typeof displayData.status_signal === 'number'
                    ? Math.max(0, Math.min(100, displayData.status_signal)).toFixed(1)
                    : '—'}
                </span>
                <StatusSignalInfo
                  breakdown={displayData.status_signal_breakdown ?? null}
                  compositeScore={typeof displayData.status_signal === 'number' ? displayData.status_signal : null}
                />
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <span className="tr-muted">Happiness</span>
                <span style={{ fontWeight: 600, color: happinessIndex != null ? 'var(--c-blue-600)' : 'var(--hf-text-secondary)' }}>
                  {happinessIndex != null ? Math.max(0, Math.min(100, happinessIndex)).toFixed(1) : '—'}
                </span>
                <HappinessInfo />
              </span>
            </div>
          </div>
        </div>

        {/* Full pillar breakdown — read-only (no rescoring controls) */}
        <ScoreDisplay
          hideSummaryCard
          data={displayData}
          priorities={priorities}
          onPrioritiesChange={setPriorities}
          placeSummary={displayData.place_summary ?? null}
        />

        {/* Footer CTA */}
        <div
          style={{
            marginTop: '2rem',
            marginBottom: '2rem',
            padding: '1.5rem',
            background: 'var(--hf-bg-subtle)',
            borderRadius: 16,
            border: '1px solid var(--hf-border)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--hf-text-primary)', marginBottom: '0.5rem' }}>
            Want to score a neighborhood?
          </div>
          <p className="tr-muted" style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>
            Trovamo analyzes livability, longevity, happiness, and community wealth across thousands of U.S. neighborhoods.
          </p>
          <Link href="/" className="hf-btn-secondary" style={{ padding: '0.85rem 1.75rem', fontSize: '0.95rem', borderRadius: 12 }}>
            Score your neighborhood →
          </Link>
        </div>
      </div>
    </main>
  )
}
