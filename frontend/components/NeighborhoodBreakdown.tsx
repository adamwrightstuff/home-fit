'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import type { ScoreResponse } from '@/types/api'
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
import ArchetypeTrajectoryInfo from '@/components/ArchetypeTrajectoryInfo'
import TrajectoryChip from '@/components/catalog/TrajectoryChip'

/**
 * Full breakdown for a pre-scored catalog neighborhood. Same view as the
 * public /p/[id] page, fed by the catalog payload instead of a saved score,
 * so it renders on the server with no live scoring.
 */
export default function NeighborhoodBreakdown({
  score,
  locationLabel,
  twinHref,
}: {
  score: ScoreResponse
  locationLabel: string
  twinHref: string
}) {
  const [priorities, setPriorities] = useState<PillarPriorities>(DEFAULT_PRIORITIES)

  const displayData = useMemo(() => {
    const rew = reweightScoreResponseFromPriorities(score, priorities)
    const li = longevityIndexFromLivabilityPillars(
      rew.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
    )
    return li != null ? { ...rew, longevity_index: li } : rew
  }, [score, priorities])

  const totalScore = displayData.total_score
  const longevityIndex = typeof displayData.longevity_index === 'number' ? displayData.longevity_index : null
  const happinessIndex = typeof displayData.happiness_index === 'number' ? displayData.happiness_index : null
  const trajectory = (displayData.status_signal_breakdown as any)?.trajectory ?? null

  return (
    <>
      <div className="hf-card" style={{ paddingBottom: '1.5rem' }}>
        <div
          style={{
            width: '100%',
            height: '260px',
            borderRadius: 12,
            overflow: 'hidden',
            marginBottom: displayData.place_summary ? '1rem' : '1.25rem',
            background: 'var(--hf-bg-subtle)',
          }}
        >
          <InteractiveMap
            location={locationLabel}
            coordinates={score.coordinates}
            completed_pillars={Object.keys(displayData.livability_pillars ?? {})}
          />
        </div>

        {displayData.place_summary && (
          <p style={{ margin: '0 0 1.25rem', fontSize: '1.05rem', lineHeight: 1.7, color: 'var(--hf-text-secondary)' }}>
            {displayData.place_summary}
          </p>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '1rem 0.75rem' }}>
          <div
            style={{
              fontSize: '2.5rem',
              fontWeight: 800,
              color: totalScore != null ? 'var(--c-purple-600)' : 'var(--hf-text-secondary)',
              lineHeight: 1.1,
            }}
          >
            {totalScore != null ? totalScore.toFixed(1) : 'n/a'}
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
                {longevityIndex != null ? longevityIndex.toFixed(1) : 'n/a'}
              </span>
              <LongevityInfo />
            </span>
            {(displayData.status_signal_breakdown?.status_label || trajectory) && (
              <span style={{ display: 'inline-flex', flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'nowrap', whiteSpace: 'nowrap' }}>
                <StatusSignalInfo
                  breakdown={displayData.status_signal_breakdown ?? null}
                  compositeScore={typeof displayData.status_signal === 'number' ? displayData.status_signal : null}
                  allowDetailModal={false}
                />
                <TrajectoryChip trajectory={trajectory} interactive={false} />
                <ArchetypeTrajectoryInfo breakdown={displayData.status_signal_breakdown ?? null} trajectory={trajectory} />
              </span>
            )}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
              <span className="tr-muted">Happiness</span>
              <span style={{ fontWeight: 600, color: happinessIndex != null ? 'var(--c-blue-600)' : 'var(--hf-text-secondary)' }}>
                {happinessIndex != null ? Math.max(0, Math.min(100, happinessIndex)).toFixed(1) : 'n/a'}
              </span>
              <HappinessInfo />
            </span>
          </div>
        </div>
      </div>

      <ScoreDisplay
        hideSummaryCard
        hideNotIncluded
        readOnlyPriorities
        data={displayData}
        priorities={priorities}
        onPrioritiesChange={setPriorities}
        placeSummary={displayData.place_summary ?? null}
        interstitialAfterCard={4}
        interstitialContent={
          <div
            style={{
              padding: '1.5rem',
              background: 'var(--hf-bg-subtle)',
              border: '1px solid var(--hf-border)',
              borderRadius: 12,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--hf-text-primary)', marginBottom: '0.4rem' }}>
              See how this neighborhood scores for your priorities
            </div>
            <p className="tr-muted" style={{ margin: '0 0 1rem', fontSize: '0.9rem', lineHeight: 1.55 }}>
              Trovamo weighs what matters to you: schools, transit, nature, space. Get your own personalized score.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <Link href="/quiz" className="hf-btn-secondary" style={{ padding: '0.7rem 1.25rem', fontSize: '0.9rem', borderRadius: 10 }}>
                Take the quiz →
              </Link>
              <Link href={twinHref} className="hf-btn-secondary" style={{ padding: '0.7rem 1.25rem', fontSize: '0.9rem', borderRadius: 10 }}>
                Find its twin →
              </Link>
            </div>
          </div>
        }
      />
    </>
  )
}
