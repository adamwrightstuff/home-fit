/**
 * Per-pillar config for the "Show details" panel on Place Results.
 * Matches docs/pillar_details_show_spec.md: scores as %, qualitative labels, no duplicate Confidence/Data Quality.
 */

import type { PillarKey } from './pillars'

export type DetailFormat = 'percent' | 'count' | 'distance' | 'qualitative' | 'text'

/** Bands for converting a numeric value to a qualitative label (e.g. median_distance_m -> "Very close" / "Short walk"). */
export interface QualitativeBand {
  max: number
  label: string
}

export interface DetailMetricBase {
  label: string
}

export interface DetailMetricPercent extends DetailMetricBase {
  path: string
  format: 'percent'
  max: number
}

export interface DetailMetricCount extends DetailMetricBase {
  path: string
  format: 'count'
  /** e.g. " businesses within ~10–15 min" */
  suffix?: string
}

export interface DetailMetricDistance extends DetailMetricBase {
  path: string
  format: 'distance'
}

export interface DetailMetricQualitative extends DetailMetricBase {
  path: string
  format: 'qualitative'
  /** Map numeric value to label using bands (check value <= band.max in order). */
  bands?: QualitativeBand[]
  /** Or map specific values to labels. */
  valueLabels?: Record<string, string>
}

export interface DetailMetricText extends DetailMetricBase {
  path: string
  format: 'text'
}

/** Static text from props (e.g. Local vs chains from includeChainsValue). */
export interface DetailMetricStatic extends DetailMetricBase {
  format: 'static'
  /** Key used by PillarCard to resolve text (e.g. 'local_vs_chains'). */
  textKey: string
}

export type DetailMetric =
  | DetailMetricPercent
  | DetailMetricCount
  | DetailMetricDistance
  | DetailMetricQualitative
  | DetailMetricText
  | DetailMetricStatic

export interface PillarDetailsSpec {
  topLine: string
  metrics: DetailMetric[]
  degradedMessage: string
}

function get(obj: unknown, path: string): unknown {
  if (!path) return obj
  const parts = path.split('.')
  let cur: unknown = obj
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[p]
  }
  return cur
}

/** Get numeric value from pillar by path. */
export function getPillarValue(pillar: Record<string, unknown>, path: string): number | undefined {
  const v = get(pillar, path)
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string') {
    const n = parseFloat(v)
    if (Number.isFinite(n)) return n
  }
  return undefined
}

/** Get string value from pillar by path. */
export function getPillarString(pillar: Record<string, unknown>, path: string): string | undefined {
  const v = get(pillar, path)
  if (v == null) return undefined
  if (Array.isArray(v)) return v.map((x) => String(x)).join(', ')
  return String(v)
}

/** Format a component score as percentage (no denominator shown). */
export function formatPercent(score: number, max: number): string {
  if (max <= 0) return '—'
  const pct = Math.round((score / max) * 100)
  return `${Math.min(100, Math.max(0, pct))}%`
}

/** Resolve qualitative label from numeric value and bands. */
export function resolveQualitative(value: number | undefined, bands?: QualitativeBand[], valueLabels?: Record<string, string>): string {
  if (value === undefined || value === null) return '—'
  if (valueLabels && valueLabels[String(value)] !== undefined) return valueLabels[String(value)]
  if (bands && bands.length > 0) {
    for (const b of bands) {
      if (value <= b.max) return b.label
    }
    return bands[bands.length - 1].label
  }
  return String(value)
}

const AMENITIES_DISTANCE_BANDS: QualitativeBand[] = [
  { max: 200, label: 'Very close (≤3 min walk)' },
  { max: 400, label: 'Short walk (3–6 min)' },
  { max: 800, label: 'Moderate walk (6–10 min)' },
  { max: 10000, label: 'Further (10+ min)' },
]

const TRANSIT_DISTANCE_BANDS: QualitativeBand[] = [
  { max: 0.5, label: 'Under 10 min walk' },
  { max: 1.5, label: '10–20 min walk' },
  { max: 100, label: 'Further' },
]

export const PILLAR_DETAILS_SPEC: Record<PillarKey, PillarDetailsSpec> = {
  natural_beauty: {
    topLine: 'Trees, water, and terrain—three ingredients that shape how “natural” this place feels.',
    metrics: [
      { label: 'Neighborhood canopy', path: 'summary.neighborhood_canopy_pct', format: 'percent', max: 100 },
      { label: 'Nearest mapped water', path: 'summary.water_proximity_km', format: 'distance' },
      { label: 'Terrain relief (local)', path: 'summary.terrain_relief_m', format: 'text' },
    ],
    degradedMessage: 'Limited data: some natural data sources were unavailable.',
  },
  active_outdoors: {
    topLine: 'Everyday parks, trails, and water access the score is built from.',
    metrics: [
      { label: 'Parks (nearby)', path: 'summary.local_parks.count', format: 'count', suffix: ' parks' },
      { label: 'Trail segments within 5 km', path: 'summary.trails.count_within_5km', format: 'count', suffix: ' segments' },
      { label: 'Nearest water access', path: 'summary.water.nearest_km', format: 'distance' },
    ],
    degradedMessage: 'Limited data: some outdoor data sources were unavailable.',
  },
  neighborhood_amenities: {
    topLine: 'How many places are walkable, how far they typically are, and how many you get within about 10 minutes.',
    metrics: [
      {
        label: 'Businesses within ~1 km',
        path: 'breakdown.home_walkability.businesses_within_1km',
        format: 'count',
        suffix: ' places',
      },
      {
        label: 'Typical distance to businesses',
        path: 'breakdown.diagnostics.median_distance_m',
        format: 'qualitative',
        bands: AMENITIES_DISTANCE_BANDS,
      },
      {
        label: 'Places within ~10 min walk',
        path: 'summary.within_10min_walk',
        format: 'count',
        suffix: ' places',
      },
    ],
    degradedMessage: 'Limited data: OSM coverage is sparse here; this score may undercount amenities.',
  },
  built_beauty: {
    topLine: 'What kind of built environment this is—form, tags from the map, and typical building age.',
    metrics: [
      { label: 'Built form', path: 'summary.built_form_label', format: 'text' },
      { label: 'Streetscape tags', path: 'summary.built_context_tags', format: 'text' },
      { label: 'Median year built', path: 'summary.median_year_built', format: 'text' },
    ],
    degradedMessage: 'Limited data: some built environment data were unavailable.',
  },
  healthcare_access: {
    topLine: 'Hospital reach, and how many everyday care points are nearby.',
    metrics: [
      { label: 'Hospitals in search', path: 'summary.hospital_count', format: 'count', suffix: ' hospitals' },
      { label: 'Nearest hospital', path: 'summary.nearest_hospital_km', format: 'distance' },
      { label: 'Pharmacies nearby', path: 'summary.pharmacy_count', format: 'count', suffix: ' pharmacies' },
    ],
    degradedMessage: 'Limited data: some healthcare data sources were unavailable.',
  },
  public_transit_access: {
    topLine: 'Distance to rail, how connected that line is, and typical commute time for this tract.',
    metrics: [
      { label: 'Walk to nearest heavy rail', path: 'summary.nearest_heavy_rail_distance_km', format: 'distance' },
      { label: 'Heavy rail connectivity', path: 'summary.heavy_rail_connectivity_tier', format: 'text' },
      { label: 'Typical commute (tract)', path: 'summary.mean_commute_minutes', format: 'text' },
    ],
    degradedMessage: 'Limited data: some transit data sources were unavailable.',
  },
  air_travel_access: {
    topLine: 'Access to major airports from this location.',
    metrics: [
      { label: 'Nearest airport', path: 'primary_airport.name', format: 'text' },
      { label: 'Distance', path: 'summary.nearest_airport_km', format: 'distance' },
      { label: 'Airports within range', path: 'summary.airport_count', format: 'count', suffix: ' airports' },
    ],
    degradedMessage: 'Limited data: airport data unavailable.',
  },
  economic_security: {
    topLine: 'Labor market stress, typical pay, and where we compared this place.',
    metrics: [
      { label: 'Unemployment rate', path: 'summary.unemployment_rate_pct', format: 'percent', max: 100 },
      { label: 'Median earnings (area)', path: 'summary.median_earnings', format: 'text' },
      { label: 'Comparison area', path: 'summary.geo_name', format: 'text' },
    ],
    degradedMessage: 'Limited data: some economic data were unavailable.',
  },
  quality_education: {
    topLine: 'Rated school quality and how many schools contribute.',
    metrics: [
      { label: 'Average school rating', path: 'summary.base_avg_rating', format: 'text' },
      { label: 'Schools with ratings', path: 'summary.total_schools_rated', format: 'count', suffix: ' schools' },
      { label: 'Top-tier schools nearby', path: 'summary.excellent_schools_count', format: 'count', suffix: ' schools' },
    ],
    degradedMessage: 'Limited data: school data unavailable or scoring disabled.',
  },
  housing_value: {
    topLine: 'Typical home price, local income, and how stretched price is versus income.',
    metrics: [
      { label: 'Median home value (tract)', path: 'summary.median_home_value', format: 'text' },
      { label: 'Median household income', path: 'summary.median_household_income', format: 'text' },
      { label: 'Price-to-income ratio', path: 'summary.price_to_income_ratio', format: 'text' },
    ],
    degradedMessage: 'Limited data: some housing or income data were unavailable.',
  },
  climate_risk: {
    topLine: 'Flood class, extra summer heat vs the region, and air pollution proxy (not another 0–100 score).',
    metrics: [
      {
        label: 'Flood zone (FEMA)',
        path: 'summary.flood_risk_tier',
        format: 'qualitative',
        valueLabels: { floodway: 'High', sfha: 'High', x_500yr: 'Moderate', d: 'Moderate', minimal: 'Low' },
      },
      { label: 'Extra heat vs region (°C)', path: 'summary.heat_excess_deg_c', format: 'text' },
      { label: 'PM2.5 proxy (µg/m³)', path: 'summary.pm25_proxy_ugm3', format: 'text' },
    ],
    degradedMessage: 'Limited data: some climate/flood data were unavailable.',
  },
  social_fabric: {
    topLine:
      'Stability from Census movers data, civic places from OpenStreetMap (or Google Places when OSM is unavailable), and engagement inputs.',
    metrics: [
      { label: 'Same-house blend (tract + place)', path: 'summary.stability_blend_pct', format: 'percent', max: 100 },
      { label: 'Civic places (non-commercial)', path: 'summary.civic_node_count', format: 'count', suffix: ' places' },
      { label: 'Modeled voter turnout (tract)', path: 'summary.voter_turnout_rate', format: 'percent', max: 1 },
    ],
    degradedMessage:
      'Limited data: Census mobility, civic places (OpenStreetMap / Places), or other community sources failed or were unavailable.',
  },
  diversity: {
    topLine: 'Which Census mix dimensions we could score, self-employment, and race/ethnic spread (entropy).',
    metrics: [
      { label: 'Mix dimensions scored', path: 'summary.components_included', format: 'text' },
      { label: 'Self-employed (tract %)', path: 'self_employed_pct', format: 'percent', max: 100 },
      { label: 'Race & ethnicity spread', path: 'breakdown.race_entropy', format: 'percent', max: 100 },
    ],
    degradedMessage: 'Limited data: Census diversity tables were unavailable.',
  },
}
