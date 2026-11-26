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
  const acq = pillars.acquaintances_nearby

  const commuteMinutes = typeof commute?.breakdown?.minutes === 'number' ? commute.breakdown.minutes : null
  const commuteScore = typeof commute?.score === 'number' ? commute.score : null
  const commuteNoRoute = commute?.breakdown?.no_route === true
  const showCommute = (commuteMinutes != null || commuteNoRoute) && commuteScore != null
  const showSocial = social && typeof social.weight === 'number' && social.weight > 0
  const showAcq = acq && typeof acq.weight === 'number' && acq.weight > 0
  if (!showCommute && !showSocial && !showAcq) return null

  type Point = { tier: 'close' | 'acquaintance'; miles: number | null; label: string | null }
  const pointsOf = (pl: any): Point[] => (Array.isArray(pl?.breakdown?.points) ? pl.breakdown.points : [])

  const formatMiles = (m: number | null) =>
    typeof m !== 'number' || !Number.isFinite(m) ? 'n/a' : m < 10 ? `${m.toFixed(1)} mi` : `${Math.round(m).toLocaleString()} mi`
  const sortedPoints = (pl: any) => [...pointsOf(pl)].sort((a, b) => (a.miles ?? Infinity) - (b.miles ?? Infinity))
  const pointList = (pl: any, fallback: string) =>
    pointsOf(pl).length > 0 && (
      <div className="mx-4 mb-3 divide-y divide-[var(--hf-border)] border-t border-[var(--hf-border)]">
        {sortedPoints(pl).map((p, i) => (
          <div key={i} className="flex items-baseline justify-between gap-3 py-1.5 text-sm text-[var(--hf-text-secondary)]">
            <span className="min-w-0 truncate">{p.label ?? fallback}</span>
            <span className="shrink-0 tabular-nums text-[var(--hf-text-tertiary)]">{formatMiles(p.miles)}</span>
          </div>
        ))}
      </div>
    )

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
            `${commuteNoRoute ? 'No route to your work hub by your chosen mode' : `${commute?.breakdown?.estimated ? 'Rough estimate, about' : 'About'} ${Math.round(commuteMinutes!)} min one way`}${
              typeof commute.breakdown?.office_days === 'number' ? `, ${commute.breakdown.office_days} office days a week` : ''
            }`,
            commuteScore
          )}
        {showSocial && (
          <div className={showCommute ? 'border-t border-[var(--hf-border)]' : ''}>
            {row(
              'Social connection',
              'Distance to the close family and friends you added. Your own preference. The shape comes from studies of older adults and caregiving, not a research-backed score.',
              typeof social.score === 'number' ? social.score : null
            )}
            {pointList(social, 'Close connection')}
          </div>
        )}
        {showAcq && (
          <div className={showCommute || showSocial ? 'border-t border-[var(--hf-border)]' : ''}>
            {row(
              'Acquaintances nearby',
              'Whether an acquaintance you added lives within about a 10-minute walk, where chance run-ins happen. Your own preference; the walk distance is borrowed from walk-to-destination research.',
              typeof acq.score === 'number' ? acq.score : null
            )}
            {pointList(acq, 'Acquaintance')}
          </div>
        )}
      </div>
    </section>
  )
}
