'use client'

import { useEffect, useMemo, useState } from 'react'
import type { ScoreResponse } from '@/types/api'
import type { PillarPriorities } from '@/components/SearchOptions'
import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'
import { useProfile } from '@/hooks/useProfile'
import { applyProfileToScore } from '@/lib/personalOverlay'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { getScoreBand } from '@/lib/pillars'
import type { WorkCommute } from '@/lib/workZones'
import { resolveNeighborhoodPriorities } from '@/lib/neighborhoodPriorities'

/**
 * The viewer's own overlays on a stored catalog score: commute to their work hub and
 * proximity to the people they added. Renders nothing when the viewer has neither, so the
 * static page stays identical for everyone else.
 */
export default function NeighborhoodPersonal({ score, workCommute }: { score: ScoreResponse; workCommute?: WorkCommute | null }) {
  const profile = useProfile()
  const [priorities, setPriorities] = useState<PillarPriorities>(DEFAULT_PRIORITIES)
  useEffect(() => {
    setPriorities(resolveNeighborhoodPriorities(window.location.search))
  }, [])

  const personal = useMemo(() => {
    const overlaid = applyProfileToScore(score, profile, { workCommute })
    return reweightScoreResponseFromPriorities(overlaid, priorities)
  }, [score, profile, priorities])

  const pillars = (personal.livability_pillars ?? {}) as Record<string, any>
  const commute = pillars.commute_time
  const social = pillars.social_connection

  const commuteMinutes = typeof commute?.breakdown?.minutes === 'number' ? commute.breakdown.minutes : null
  const commuteScore = typeof commute?.score === 'number' ? commute.score : null
  const showCommute = commuteMinutes != null && commuteScore != null
  const showSocial = social && typeof social.weight === 'number' && social.weight > 0
  if (!showCommute && !showSocial) return null

  const points: Array<{ tier: 'close' | 'acquaintance'; minutes: number | null; label: string | null }> =
    Array.isArray(social?.breakdown?.points) ? social.breakdown.points : []

  const formatTravel = (m: number | null) => {
    if (typeof m !== 'number' || !Number.isFinite(m)) return 'n/a'
    if (m < 60) return `${Math.round(m)} min`
    if (m < 240) return `${Math.floor(m / 60)} hr ${Math.round(m % 60)} min`
    return 'Over 4 hr'
  }
  const sortedPoints = [...points].sort((a, b) => (a.minutes ?? Infinity) - (b.minutes ?? Infinity))

  const row = (title: string, note: string, value: number | null) => {
    const band = value != null ? getScoreBand(value) : null
    return (
      <div className="px-4 py-3">
        <div className="flex items-baseline justify-between gap-3">
          <div className="min-w-0">
            <span className="text-sm font-semibold text-[var(--hf-text-primary)]">{title}</span>
            <div className="text-xs text-[var(--hf-text-tertiary)]">{note}</div>
          </div>
          <div className="flex shrink-0 items-baseline gap-2">
            {band && (
              <span className="text-[0.7rem] font-semibold" style={{ color: band.color }}>
                {band.label}
              </span>
            )}
            <span className="w-8 text-right text-sm font-bold tabular-nums text-[var(--hf-text-primary)]">
              {value != null ? value.toFixed(0) : 'n/a'}
            </span>
          </div>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
          <div
            className="h-full rounded-full"
            style={{
              width: `${value != null ? Math.max(0, Math.min(100, value)) : 0}%`,
              background: band?.color ?? 'var(--hf-border)',
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <section className="mb-8" aria-label="Your fit">
      <h2 className="mb-3 text-lg font-bold text-[var(--hf-text-primary)]">Your fit</h2>
      <div className="overflow-hidden rounded-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)]">
        {showCommute &&
          row(
            'Commute',
            `About ${Math.round(commuteMinutes!)} min one way${
              typeof commute.breakdown?.office_days === 'number' ? `, ${commute.breakdown.office_days} office days a week` : ''
            }`,
            commuteScore
          )}
        {showSocial && (
          <div className={showCommute ? 'border-t border-[var(--hf-border)]' : ''}>
            {row(
              'Social connection',
              'Proximity to the people you added. A rough estimate, not one of the 13 research-backed pillars.',
              typeof social.score === 'number' ? social.score : null
            )}
            {points.length > 0 && (
              <div className="mx-4 mb-3 divide-y divide-[var(--hf-border)] border-t border-[var(--hf-border)]">
                {sortedPoints.map((p, i) => (
                  <div key={i} className="flex items-baseline justify-between gap-3 py-1.5 text-sm text-[var(--hf-text-secondary)]">
                    <span className="min-w-0 truncate">{p.label ?? (p.tier === 'close' ? 'Close connection' : 'Acquaintance')}</span>
                    <span className="shrink-0 tabular-nums text-[var(--hf-text-tertiary)]">{formatTravel(p.minutes)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
