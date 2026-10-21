import { isCatalogMetro, type CatalogMetro } from '@/lib/catalogMetros'
import type { WorkCommute } from './workZones'
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
  | 'commute_time'
  | 'social_connection'

export const PILLAR_INDEX_MODES: { id: CatalogMapIndexMode; label: string }[] = [
  { id: 'active_outdoors', label: 'Active outdoors' },
  { id: 'neighborhood_amenities', label: 'Amenities' },
  { id: 'natural_beauty', label: 'Natural beauty' },
  { id: 'public_transit_access', label: 'Transit' },
  { id: 'climate_risk', label: 'Climate risk' },
  { id: 'housing_value', label: 'Housing value' },
  { id: 'social_fabric', label: 'Social fabric' },
  { id: 'healthcare_access', label: 'Healthcare' },
  { id: 'economic_opportunity', label: 'Economic' },
  { id: 'quality_education', label: 'Education' },
  { id: 'community_safety', label: 'Safety' },
  { id: 'diversity', label: 'Diversity' },
  { id: 'air_travel_access', label: 'Air travel' },
  { id: 'commute_time', label: 'Commute time' },
  { id: 'social_connection', label: 'Social proximity' },
]

export function isPillarIndexMode(mode: CatalogMapIndexMode): boolean {
  return PILLAR_INDEX_MODES.some((m) => m.id === mode)
}

/** Derived climate indicators joined from catalog_climate_profiles.jsonl. */
export interface ClimateIndicators {
  jan_f: number       // mean January temp °F
  jul_f: number       // mean July temp °F
  swing_f: number     // jul_f - jan_f (seasonal variation)
  months_below_freezing: number // months whose mean temp is under 32°F
  coldest_month_f: number // mean temp of the coldest month °F (Köppen cold-winter test)
  annual_precip_in: number
  avg_solar: number   // kWh/m²/day (sunshine proxy)
}

/** Parsed line from `nyc_metro_place_catalog_scores_merged.jsonl`. */
export interface CatalogMapPlace {
  catalog: CatalogRow
  score: ScoreResponse
  climate?: ClimateIndicators
  cbd_transit_minutes?: number | null
  cbd_transit_dest?: 'gct' | 'penn' | null
  /** Precomputed fastest weekday-morning minutes to each work zone. */
  work_commute?: WorkCommute | null
  /** Set when a work zone is active: replaces the CBD line, e.g. "Stamford: 21 min transit · 38 min drive". */
  commute_text?: string | null
  /** Work zone active but no precomputed time to it; commute filter skips this place. */
  commute_off_zone?: boolean
}

/** After `metro=all`, each place is tagged with its source metro. */
export type CatalogMapPlaceWithMetro = CatalogMapPlace & { metro: CatalogMetro }

export interface CatalogMapApiResponse {
  places: CatalogMapPlace[] | CatalogMapPlaceWithMetro[]
  source: string
}

export function catalogRowKey(c: Pick<CatalogRow, 'name' | 'county_borough' | 'state_abbr'>): string {
  return `${c.name}|${c.county_borough}|${c.state_abbr}`
}

const SF_COUNTIES = new Set(['San Francisco', 'San Mateo', 'Santa Clara', 'Alameda', 'Contra Costa', 'Marin'])
const PHILLY_NJ_COUNTIES = new Set(['Burlington', 'Camden', 'Gloucester', 'Salem'])

/**
 * Fallback when a place carries no `metro` tag (the API tags every place; this only runs on stale
 * data). State alone decides unambiguous states; CA and NJ are split by county. Add new states here.
 */
// BEGIN GENERATED infer (scripts/metro_agent/registry.py; do not edit by hand)
function inferFromRegistry(state: string, county: string): CatalogMetro | null {
  if (state === 'TX' && ['Collin', 'Dallas', 'Denton', 'Ellis', 'Hunt', 'Johnson', 'Kaufman', 'Parker', 'Rockwall', 'Tarrant', 'Wise'].includes(county)) return 'dallas'
  if (state === 'TX' && ['Austin', 'Brazoria', 'Chambers', 'Fort Bend', 'Galveston', 'Harris', 'Liberty', 'Montgomery', 'Waller'].includes(county)) return 'houston'
  if (state === 'TX' && ['Atascosa', 'Bandera', 'Bexar', 'Comal', 'Guadalupe', 'Kendall', 'Medina', 'Wilson'].includes(county)) return 'san_antonio'
  if (state === 'CA' && ['El Dorado', 'Placer', 'Sacramento', 'Yolo'].includes(county)) return 'sacramento'
  if (state === 'FL' && ['Lake', 'Orange', 'Osceola', 'Seminole'].includes(county)) return 'orlando'
  if (state === 'FL' && ['Hernando', 'Hillsborough', 'Pasco', 'Pinellas'].includes(county)) return 'tampa'
  if (state === 'FL' && ['Broward', 'Miami-Dade', 'Palm Beach'].includes(county)) return 'miami'
  if (state === 'NC' && ['Cabarrus', 'Gaston', 'Iredell', 'Lincoln', 'Mecklenburg', 'Rowan', 'Union'].includes(county)) return 'charlotte'
  if (state === 'NC' && ['Franklin', 'Johnston', 'Wake'].includes(county)) return 'raleigh'
  if (state === 'AZ') return 'phoenix'
  if (state === 'NV') return 'las_vegas'
  return null
}
// END GENERATED infer

export function inferCatalogMetro(p: CatalogMapPlace & { metro?: CatalogMetro }): CatalogMetro {
  if (isCatalogMetro(p.metro)) return p.metro
  const state = p.catalog.state_abbr
  const county = p.catalog.county_borough
  const fromRegistry = inferFromRegistry(state, county)
  if (fromRegistry) return fromRegistry
  if (state === 'WA') return 'seattle'
  if (state === 'TX') return 'austin'
  if (state === 'IL' || state === 'IN') return 'chicago'
  if (state === 'PA' || state === 'DE' || state === 'MD') return 'philadelphia'
  if (state === 'NJ' && PHILLY_NJ_COUNTIES.has(county)) return 'philadelphia'
  if (state === 'CA') return SF_COUNTIES.has(county) ? 'sf' : 'la'
  return 'nyc'
}
