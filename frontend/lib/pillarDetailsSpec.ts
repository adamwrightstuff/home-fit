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
    topLine: 'Natural scenery based on trees, water, and surrounding landscape.',
    metrics: [
      { label: 'Tree score', path: 'summary.tree_score', format: 'percent', max: 100 },
      { label: 'Neighborhood canopy', path: 'summary.neighborhood_canopy_pct', format: 'percent', max: 100 },
      { label: 'Local canopy', path: 'summary.local_canopy_pct', format: 'percent', max: 100 },
      { label: 'Extended canopy', path: 'summary.extended_canopy_pct', format: 'percent', max: 100 },
    ],
    degradedMessage: 'Limited data: some natural data sources were unavailable.',
  },
  active_outdoors: {
    topLine: 'Access to parks, trails, and water for an active lifestyle.',
    metrics: [
      { label: 'Daily urban outdoors', path: 'breakdown.daily_urban_outdoors', format: 'percent', max: 30 },
      { label: 'Wild adventure', path: 'breakdown.wild_adventure', format: 'percent', max: 50 },
      { label: 'Waterfront lifestyle', path: 'breakdown.waterfront_lifestyle', format: 'percent', max: 20 },
    ],
    degradedMessage: 'Limited data: some outdoor data sources were unavailable.',
  },
  neighborhood_amenities: {
    topLine: 'Walkable access to daily needs, social spots, and services.',
    metrics: [
      { label: 'Home walkability', path: 'breakdown.home_walkability.score', format: 'percent', max: 60 },
      { label: 'Daily needs nearby', path: 'breakdown.home_walkability.businesses_within_1km', format: 'count', suffix: ' businesses within ~10–15 min' },
      { label: 'Town center & vibrancy', path: 'breakdown.location_quality', format: 'percent', max: 40 },
      { label: 'Local vs chains', format: 'static', textKey: 'local_vs_chains' },
    ],
    degradedMessage: 'Limited data: OSM coverage is sparse here; this score may undercount amenities.',
  },
  built_beauty: {
    topLine: 'Street and building design, diversity, and human scale.',
    metrics: [
      { label: 'Architecture diversity', path: 'details.architectural_analysis.metrics.diversity_score', format: 'percent', max: 100 },
      { label: 'Street character', path: 'summary.diversity_score', format: 'percent', max: 100 },
    ],
    degradedMessage: 'Limited data: some built environment data were unavailable.',
  },
  healthcare_access: {
    topLine: 'Access to hospitals, urgent care, clinics, and pharmacies.',
    metrics: [
      { label: 'Hospital access', path: 'breakdown.breakdown.hospital_access', format: 'percent', max: 35 },
      { label: 'Primary care', path: 'breakdown.breakdown.primary_care', format: 'percent', max: 25 },
      { label: 'Specialized care', path: 'breakdown.breakdown.specialized_care', format: 'percent', max: 15 },
      { label: 'Emergency services', path: 'breakdown.breakdown.emergency_services', format: 'percent', max: 10 },
      { label: 'Pharmacies', path: 'breakdown.breakdown.pharmacies', format: 'percent', max: 15 },
      { label: 'Facilities', path: 'summary.hospital_count', format: 'count', suffix: ' hospitals' },
    ],
    degradedMessage: 'Limited data: some healthcare data sources were unavailable.',
  },
  public_transit_access: {
    topLine: 'Access to rail and key transit within walking distance.',
    metrics: [
      { label: 'Heavy rail', path: 'breakdown.breakdown.heavy_rail', format: 'percent', max: 100 },
      { label: 'Light rail', path: 'breakdown.breakdown.light_rail', format: 'percent', max: 100 },
      { label: 'Bus', path: 'breakdown.breakdown.bus', format: 'percent', max: 100 },
      { label: 'Nearest heavy rail', path: 'summary.nearest_heavy_rail_distance_km', format: 'distance' },
      { label: 'Connectivity', path: 'summary.heavy_rail_connectivity_tier', format: 'text' },
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
    topLine: 'Local job market strength for your focus (or general economic health).',
    metrics: [
      { label: 'Job market fit', path: 'breakdown.base_score', format: 'percent', max: 100 },
      { label: 'Area', path: 'summary.division', format: 'text' },
    ],
    degradedMessage: 'Limited data: some economic data were unavailable.',
  },
  quality_education: {
    topLine: 'Quality and availability of nearby schools (when enabled).',
    metrics: [
      { label: 'Average school rating', path: 'summary.base_avg_rating', format: 'percent', max: 10 },
      { label: 'Schools rated', path: 'summary.total_schools_rated', format: 'count', suffix: ' schools' },
      { label: 'Excellent schools', path: 'summary.excellent_schools_count', format: 'count', suffix: ' excellent' },
    ],
    degradedMessage: 'Limited data: school data unavailable or scoring disabled.',
  },
  housing_value: {
    topLine: 'How far your money goes on housing here.',
    metrics: [
      { label: 'Local affordability', path: 'breakdown.breakdown.local_affordability', format: 'percent', max: 50 },
      { label: 'Space', path: 'breakdown.breakdown.space', format: 'percent', max: 30 },
      { label: 'Value efficiency', path: 'breakdown.breakdown.value_efficiency', format: 'percent', max: 20 },
      { label: 'Median home value', path: 'summary.median_home_value', format: 'text' },
    ],
    degradedMessage: 'Limited data: some housing or income data were unavailable.',
  },
  climate_risk: {
    topLine: 'Exposure to flooding, heat, and air quality.',
    metrics: [
      { label: 'Flood risk', path: 'summary.flood_risk_tier', format: 'qualitative', valueLabels: { floodway: 'High', sfha: 'High', x_500yr: 'Moderate', d: 'Moderate', minimal: 'Low' } },
      { label: 'Heat exposure', path: 'breakdown.lst_score', format: 'percent', max: 100 },
      { label: 'Air quality', path: 'breakdown.aqi_score', format: 'percent', max: 100 },
      { label: 'Climate trend', path: 'breakdown.climate_trend_score_0_100', format: 'percent', max: 100 },
    ],
    degradedMessage: 'Limited data: some climate/flood data were unavailable.',
  },
  social_fabric: {
    topLine: 'Community stability and civic places to connect.',
    metrics: [
      { label: 'Residential stability', path: 'summary.same_house_pct', format: 'percent', max: 100 },
      { label: 'Civic & third places', path: 'summary.civic_node_count_800m', format: 'count', suffix: ' civic places nearby' },
      { label: 'Community strength', path: 'summary.voter_registration_rate', format: 'percent', max: 1 },
    ],
    degradedMessage: 'Limited data: some community data were unavailable.',
  },
}
