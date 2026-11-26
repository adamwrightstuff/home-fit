'use client'

import { useEffect, useMemo, useState } from 'react'
import type { ScoreResponse } from '@/types/api'
import { applyUserIncomeToScore, applyScenerySubPreferencesToScore, reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { applyCommuteAndPeople, applyExplorerScoreAdjustments, readCompareContext, type CompareContext } from '@/lib/explorerScoreAdjust'
import { HOMEFIT_COPY, HAPPINESS_INDEX_COPY } from '@/lib/pillars'
import type { WorkCommute } from '@/lib/workZones'

function ScoreHero({ label, value, tooltip, accent }: { label: string; value: number | null; tooltip: string; accent: string }) {
  return (
    <div
      className="flex flex-col items-center rounded-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] px-4 py-5"
      title={tooltip}
    >
      <div className="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-[var(--hf-text-tertiary)]">{label}</div>
      <div className="mt-1 text-4xl font-bold tabular-nums" style={{ color: accent }}>
        {value != null && Number.isFinite(value) ? value.toFixed(0) : 'No data'}
      </div>
      <div className="mt-1 text-[0.7rem] text-[var(--hf-text-tertiary)]">out of 100</div>
    </div>
  )
}

/**
 * The HomeFit and Happiness headline. With no Explorer session it shows the stored catalog score. When the visitor came
 * from the Explorer it applies the same adjustments the list applied (income, school type, scenery and outdoors
 * preferences, work hub, people, weights), so the page and the list row show the same number.
 */
export default function NeighborhoodHeadline({
  score,
  workCommute,
  placeName,
  lat,
  lon,
}: {
  score: ScoreResponse
  workCommute?: WorkCommute | null
  placeName: string
  lat?: number | string | null
  lon?: number | string | null
}) {
  const [ctx, setCtx] = useState<CompareContext | null>(null)
  useEffect(() => {
    setCtx(readCompareContext())
  }, [])

  const shown = useMemo(() => {
    if (!ctx) return score
    const home = ctx.currentHome
    const isCurrentHome = !!home && home.name === placeName
    let out = ctx.householdIncome ? applyUserIncomeToScore(score, ctx.householdIncome, isCurrentHome ? home!.monthlyCost : null) : score
    out = applyExplorerScoreAdjustments(out, ctx.filters)
    out = applyCommuteAndPeople(out, { workCommute: workCommute ?? null, lat, lon }, ctx)
    const nb = ctx.filters.filterNbTypes ?? []
    const ao = ctx.filters.filterAoTypes ?? []
    if ((nb.length > 0 && nb.length < 4) || (ao.length > 0 && ao.length < 3)) {
      out = applyScenerySubPreferencesToScore(out, ao, null, nb)
    }
    return reweightScoreResponseFromPriorities(out, ctx.priorities)
  }, [ctx, score, workCommute, placeName, lat, lon])

  return (
    <section className="mb-6 grid grid-cols-2 gap-3" aria-label="Scores">
      <ScoreHero
        label="HomeFit"
        value={typeof shown.total_score === 'number' ? shown.total_score : null}
        tooltip={HOMEFIT_COPY.tooltip}
        accent="var(--hf-primary-1)"
      />
      <ScoreHero
        label="Happiness"
        value={typeof shown.happiness_index === 'number' ? shown.happiness_index : null}
        tooltip={HAPPINESS_INDEX_COPY.tooltip}
        accent="var(--tr-accent-800)"
      />
    </section>
  )
}
