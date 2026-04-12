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

/** After `metro=all`, each place is tagged with its source metro. */
export type CatalogMapPlaceWithMetro = CatalogMapPlace & { metro: 'nyc' | 'la' }

export interface CatalogMapApiResponse {
  places: CatalogMapPlace[] | CatalogMapPlaceWithMetro[]
  source: string
}

export function catalogRowKey(c: Pick<CatalogRow, 'name' | 'county_borough' | 'state_abbr'>): string {
  return `${c.name}|${c.county_borough}|${c.state_abbr}`
}

/** Single-metro API responses omit `metro`; infer from state when missing. */
export function inferCatalogMetro(p: CatalogMapPlace & { metro?: 'nyc' | 'la' }): 'nyc' | 'la' {
  if (p.metro === 'nyc' || p.metro === 'la') return p.metro
  return p.catalog.state_abbr === 'CA' ? 'la' : 'nyc'
}
