import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { PILLAR_META, PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { PillarPriorities } from '@/components/SearchOptions'
import type { CatalogMapIndexMode, CatalogMapPlace } from '@/lib/catalogMapTypes'
import { catalogRowKey } from '@/lib/catalogMapTypes'
import { getScoreBandColor } from '@/lib/pillars'

/** Distinct colors for Status Signal archetypes (map layer). */
const ARCHETYPE_COLORS: Record<string, string> = {
  Patrician: '#5c4d7d',
  Parvenu: '#0f766e',
  Poseur: '#a855f7',
  Plebeian: '#78716c',
  Typical: '#94a3b8',
}

export function archetypeBubbleColor(archetype: string | undefined | null): string {
  if (!archetype) return '#94a3b8'
  return ARCHETYPE_COLORS[archetype] ?? '#64748b'
}

/** 0–100 score → band color (same palette as score badges). */
export function numericScoreColor(score: number | null | undefined): string {
  if (score == null || !Number.isFinite(score)) return '#94a3b8'
  return getScoreBandColor(score)
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
    let color: string
    if (mode === 'status') {
      color = archetypeBubbleColor(archetype)
    } else {
      color = numericScoreColor(v)
    }
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
