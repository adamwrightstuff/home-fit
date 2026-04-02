import type { ScoreResponse } from '@/types/api'

/** One row from `data/nyc_metro_place_catalog.csv` embedded in catalog scores JSONL. */
export interface CatalogRow {
  name: string
  type: string
  county_borough: string
  state_full: string
  state_abbr: string
  lat: number
  lon: number
  search_query: string
}

export type CatalogMapIndexMode = 'homefit' | 'longevity' | 'happiness' | 'status'

/** Parsed line from `nyc_metro_place_catalog_scores_merged.jsonl`. */
export interface CatalogMapPlace {
  catalog: CatalogRow
  score: ScoreResponse
}

export interface CatalogMapApiResponse {
  places: CatalogMapPlace[]
  source: string
}

export function catalogRowKey(c: Pick<CatalogRow, 'name' | 'county_borough' | 'state_abbr'>): string {
  return `${c.name}|${c.county_borough}|${c.state_abbr}`
}
