import type { ScoreResponse } from '@/types/api'

/** One-shot handoff from catalog map → /results (Option A). */
export const CATALOG_RESULTS_HYDRATE_KEY = 'homefit_catalog_hydrate'

export type CatalogResultsHydratePayload = {
  v: 1
  /** Must match `buildResultsCacheKey` for the `/results` URL we navigate to. */
  cacheKey: string
  score: ScoreResponse
}

export function writeCatalogResultsHydrate(payload: CatalogResultsHydratePayload): void {
  try {
    window.sessionStorage?.setItem(CATALOG_RESULTS_HYDRATE_KEY, JSON.stringify(payload))
  } catch {
    // quota / private mode — results page will fall back to live score
  }
}

export function readAndConsumeCatalogResultsHydrate(expectedCacheKey: string): ScoreResponse | null {
  try {
    const raw = window.sessionStorage?.getItem(CATALOG_RESULTS_HYDRATE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<CatalogResultsHydratePayload>
    window.sessionStorage?.removeItem(CATALOG_RESULTS_HYDRATE_KEY)
    if (parsed?.v !== 1 || !parsed.score || typeof parsed.cacheKey !== 'string') return null
    if (parsed.cacheKey !== expectedCacheKey) return null
    return parsed.score as ScoreResponse
  } catch {
    try {
      window.sessionStorage?.removeItem(CATALOG_RESULTS_HYDRATE_KEY)
    } catch {
      // ignore
    }
    return null
  }
}
