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

export type CatalogMapIndexMode =
  | 'homefit'
  | 'longevity'
  | 'happiness'
  | 'status'
  | 'active_outdoors'
  | 'neighborhood_amenities'
  | 'natural_beauty'
  | 'public_transit_access'
  | 'climate_risk'
  | 'housing_value'
  | 'social_fabric'
  | 'built_environment'
  | 'healthcare_access'
  | 'economic_opportunity'
  | 'quality_education'
  | 'community_safety'
  | 'diversity'
  | 'air_travel_access'

export const PILLAR_INDEX_MODES: { id: CatalogMapIndexMode; label: string }[] = [
  { id: 'active_outdoors', label: 'Active outdoors' },
  { id: 'neighborhood_amenities', label: 'Amenities' },
  { id: 'natural_beauty', label: 'Natural beauty' },
  { id: 'public_transit_access', label: 'Transit' },
  { id: 'climate_risk', label: 'Climate risk' },
  { id: 'housing_value', label: 'Housing value' },
  { id: 'social_fabric', label: 'Social fabric' },
  { id: 'built_environment', label: 'Built environment' },
  { id: 'healthcare_access', label: 'Healthcare' },
  { id: 'economic_opportunity', label: 'Economic' },
  { id: 'quality_education', label: 'Education' },
  { id: 'community_safety', label: 'Safety' },
  { id: 'diversity', label: 'Diversity' },
  { id: 'air_travel_access', label: 'Air travel' },
]

export function isPillarIndexMode(mode: CatalogMapIndexMode): boolean {
  return PILLAR_INDEX_MODES.some((m) => m.id === mode)
}

/** Derived climate indicators joined from catalog_climate_profiles.jsonl. */
export interface ClimateIndicators {
  jan_f: number       // mean January temp °F
  jul_f: number       // mean July temp °F
  swing_f: number     // jul_f - jan_f (seasonal variation)
  annual_precip_in: number
  avg_solar: number   // kWh/m²/day (sunshine proxy)
}

/** Parsed line from `nyc_metro_place_catalog_scores_merged.jsonl`. */
export interface CatalogMapPlace {
  catalog: CatalogRow
  score: ScoreResponse
  climate?: ClimateIndicators
}

/** After `metro=all`, each place is tagged with its source metro. */
export type CatalogMapPlaceWithMetro = CatalogMapPlace & { metro: 'nyc' | 'la' | 'sf' }

export interface CatalogMapApiResponse {
  places: CatalogMapPlace[] | CatalogMapPlaceWithMetro[]
  source: string
}

export function catalogRowKey(c: Pick<CatalogRow, 'name' | 'county_borough' | 'state_abbr'>): string {
  return `${c.name}|${c.county_borough}|${c.state_abbr}`
}

const SF_COUNTIES = new Set(['San Francisco', 'San Mateo', 'Santa Clara', 'Alameda', 'Contra Costa', 'Marin'])

/** Single-metro API responses omit `metro`; infer from catalog fields when missing. */
export function inferCatalogMetro(p: CatalogMapPlace & { metro?: 'nyc' | 'la' | 'sf' }): 'nyc' | 'la' | 'sf' {
  if (p.metro === 'nyc' || p.metro === 'la' || p.metro === 'sf') return p.metro
  if (p.catalog.state_abbr === 'CA') {
    return SF_COUNTIES.has(p.catalog.county_borough) ? 'sf' : 'la'
  }
  return 'nyc'
}
