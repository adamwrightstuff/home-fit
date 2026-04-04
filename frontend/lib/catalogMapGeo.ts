import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { PILLAR_META, PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { PillarPriorities } from '@/components/SearchOptions'
import type { CatalogMapIndexMode, CatalogMapPlace } from '@/lib/catalogMapTypes'
import { catalogRowKey } from '@/lib/catalogMapTypes'
import {
  catalogModeToRamp,
  mapBubbleStroke,
  mapBubbleStrokeStatusArchetype,
  scoreBandFill,
  scoreBandFillStatusArchetype,
} from '@/lib/indexColorSystem'

/** 0–100 score → bubble fill from active index ramp; Status uses archetype hue + score band. */
export function numericScoreColorForMode(
  score: number | null | undefined,
  mode: CatalogMapIndexMode,
  statusArchetype?: string | null
): string {
  if (score == null || !Number.isFinite(score)) return '#94a3b8'
  if (mode === 'status') {
    return scoreBandFillStatusArchetype(statusArchetype ?? null, score)
  }
  return scoreBandFill(catalogModeToRamp(mode), score)
}

function catalogBubbleStrokeForFeature(
  mode: CatalogMapIndexMode,
  score: number | null,
  statusArchetype: string | null
): string {
  if (score == null || !Number.isFinite(score)) {
    return 'rgba(100, 116, 139, 0.55)'
  }
  if (mode === 'status') {
    return mapBubbleStrokeStatusArchetype(statusArchetype)
  }
  return mapBubbleStroke(catalogModeToRamp(mode))
}

function displayScoreForMode(
  place: CatalogMapPlace,
  mode: CatalogMapIndexMode,
  priorities: PillarPriorities
): { v: number | null; archetype: string | null } {
  if (mode === 'homefit') {
    const rw = reweightScoreResponseFromPriorities(place.score, priorities)
    return { v: rw.total_score, archetype: null }
  }
  const s = place.score
  if (mode === 'longevity') {
    return { v: typeof s.longevity_index === 'number' ? s.longevity_index : null, archetype: null }
  }
  if (mode === 'happiness') {
    return { v: typeof s.happiness_index === 'number' ? s.happiness_index : null, archetype: null }
  }
  const archetype = s.status_signal_breakdown?.archetype ?? null
  return {
    v: typeof s.status_signal === 'number' ? s.status_signal : null,
    archetype,
  }
}

export function buildCatalogFeatureCollection(
  places: CatalogMapPlace[],
  mode: CatalogMapIndexMode,
  priorities: PillarPriorities
) {
  const features = places.map((p) => {
    const { v, archetype } = displayScoreForMode(p, mode, priorities)
    const key = catalogRowKey(p.catalog)
    const color = numericScoreColorForMode(v, mode, mode === 'status' ? archetype : undefined)
    const strokeColor = catalogBubbleStrokeForFeature(mode, v, archetype)
    return {
      type: 'Feature' as const,
      id: key,
      geometry: {
        type: 'Point' as const,
        coordinates: [p.catalog.lon, p.catalog.lat] as [number, number],
      },
      properties: {
        key,
        name: p.catalog.name,
        v: v ?? 0,
        color,
        strokeColor,
        archetype: archetype ?? '',
        hasValue: v != null && Number.isFinite(v),
      },
    }
  })
  return { type: 'FeatureCollection' as const, features }
}

/** Top pillar names for peek card (by absolute contribution when HomeFit reweighted; else by raw pillar score). */
export function topPillarCallouts(
  place: CatalogMapPlace,
  mode: CatalogMapIndexMode,
  priorities: PillarPriorities,
  limit: number
): string[] {
  const rw =
    mode === 'homefit'
      ? reweightScoreResponseFromPriorities(place.score, priorities)
      : place.score
  const pillars = rw.livability_pillars as unknown as Record<
    string,
    { score?: number; contribution?: number } | undefined
  >
  const ranked = PILLAR_ORDER.map((k) => {
    const pl = pillars[k]
    const score = typeof pl?.score === 'number' ? pl.score : NaN
    const contribution = typeof pl?.contribution === 'number' ? Math.abs(pl.contribution) : 0
    return { k, score, contribution }
  })
    .filter((x) => Number.isFinite(x.score))
    .sort((a, b) => {
      if (mode === 'homefit') return b.contribution - a.contribution
      return b.score - a.score
    })
  return ranked.slice(0, limit).map((r) => PILLAR_META[r.k as PillarKey].name)
}

/** All four index values for catalog peek UI (scores colored per index ramp). */
export function getAllCatalogIndexDisplay(
  place: CatalogMapPlace,
  priorities: PillarPriorities
): {
  homefit: number | null
  longevity: number | null
  happiness: number | null
  statusSignal: number | null
  archetype: string | null
  archetypeBadge: string | null
} {
  const rw = reweightScoreResponseFromPriorities(place.score, priorities)
  const s = place.score
  const br = s.status_signal_breakdown
  const archetype = br?.archetype ?? null
  const archetypeBadge =
    archetype && br?.status_label
      ? `${archetype} · ${br.status_label}`
      : archetype || (typeof br?.status_label === 'string' ? br.status_label : null)
  return {
    homefit: typeof rw.total_score === 'number' && Number.isFinite(rw.total_score) ? rw.total_score : null,
    longevity: typeof s.longevity_index === 'number' ? s.longevity_index : null,
    happiness: typeof s.happiness_index === 'number' ? s.happiness_index : null,
    statusSignal: typeof s.status_signal === 'number' ? s.status_signal : null,
    archetype,
    archetypeBadge,
  }
}

export type CatalogStandoutChip = {
  pillarKey: PillarKey
  name: string
  score: number
  tier: 'top' | 'bottom'
}

/** Top 2 + weakest 1 pillar chips (green vs coral tint in UI). */
export function getStandoutPillarChips(
  place: CatalogMapPlace,
  mode: CatalogMapIndexMode,
  priorities: PillarPriorities
): CatalogStandoutChip[] {
  const rw =
    mode === 'homefit'
      ? reweightScoreResponseFromPriorities(place.score, priorities)
      : place.score
  const pillars = rw.livability_pillars as unknown as Record<
    string,
    { score?: number; contribution?: number } | undefined
  >
  const ranked = PILLAR_ORDER.map((k) => {
    const pl = pillars[k]
    const score = typeof pl?.score === 'number' ? pl.score : NaN
    const contribution = typeof pl?.contribution === 'number' ? Math.abs(pl.contribution) : 0
    return { k: k as PillarKey, score, contribution }
  })
    .filter((x) => Number.isFinite(x.score))
    .sort((a, b) => {
      if (mode === 'homefit') return b.contribution - a.contribution
      return b.score - a.score
    })
  if (ranked.length === 0) return []
  const out: CatalogStandoutChip[] = []
  const topSlots = Math.min(2, ranked.length)
  for (let i = 0; i < topSlots; i++) {
    const r = ranked[i]!
    out.push({ pillarKey: r.k, name: PILLAR_META[r.k].name, score: r.score, tier: 'top' })
  }
  if (ranked.length >= 3) {
    const last = ranked[ranked.length - 1]!
    if (!out.some((c) => c.pillarKey === last.k)) {
      out.push({ pillarKey: last.k, name: PILLAR_META[last.k].name, score: last.score, tier: 'bottom' })
    }
  }
  return out
}

export function displayIndexValue(
  place: CatalogMapPlace,
  mode: CatalogMapIndexMode,
  priorities: PillarPriorities
): { label: string; value: string; sub?: string } {
  const { v, archetype } = displayScoreForMode(place, mode, priorities)
  if (mode === 'status') {
    const tier = place.score.status_signal_breakdown?.signal_strength_label
    return {
      label: 'Status Signal',
      value: v != null && Number.isFinite(v) ? v.toFixed(1) : '—',
      sub: archetype ? `${archetype}${tier ? ` · ${tier}` : ''}` : tier ?? undefined,
    }
  }
  const labels: Record<CatalogMapIndexMode, string> = {
    homefit: 'HomeFit',
    longevity: 'Longevity',
    happiness: 'Happiness',
    status: 'Status Signal',
  }
  return {
    label: labels[mode],
    value: v != null && Number.isFinite(v) ? v.toFixed(1) : '—',
  }
}
