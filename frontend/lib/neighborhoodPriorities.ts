import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'
import type { PillarPriorities, PriorityLevel } from '@/components/SearchOptions'
import { PILLAR_ORDER, type PillarKey } from '@/lib/pillars'

const LEVELS: PriorityLevel[] = ['None', 'Low', 'Medium', 'High']
const KEYS = [...PILLAR_ORDER, 'natural_beauty', 'commute_time', 'social_connection'] as PillarKey[]

/** Merge an unknown priorities object over the defaults, keeping only valid levels. */
export function mergePriorities(source: unknown): PillarPriorities {
  const merged = { ...DEFAULT_PRIORITIES } as Record<string, PriorityLevel>
  if (source && typeof source === 'object') {
    const src = source as Record<string, unknown>
    for (const k of KEYS) {
      const v = src[k]
      if (LEVELS.includes(v as PriorityLevel)) merged[k] = v as PriorityLevel
    }
  }
  return merged as unknown as PillarPriorities
}

/** `?priorities=` JSON first (shared links), then the visitor's saved weights, else defaults. */
export function resolveNeighborhoodPriorities(search: string): PillarPriorities {
  try {
    const raw = new URLSearchParams(search).get('priorities')
    if (raw) return mergePriorities(JSON.parse(raw))
  } catch { /* fall through */ }
  try {
    const stored = localStorage.getItem('homefit_search_options')
    if (stored) {
      const parsed = JSON.parse(stored)
      return mergePriorities(parsed.priorities ?? parsed)
    }
  } catch { /* fall through */ }
  return { ...DEFAULT_PRIORITIES }
}

/** Link to a neighborhood page carrying the visitor's weights (omitted when default). */
export function neighborhoodHref(slug: string, priorities: PillarPriorities): string {
  const json = JSON.stringify(priorities)
  const base = `/neighborhoods/${slug}`
  return json === JSON.stringify(DEFAULT_PRIORITIES) ? base : `${base}?priorities=${encodeURIComponent(json)}`
}
