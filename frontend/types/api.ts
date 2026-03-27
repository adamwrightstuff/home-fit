// TypeScript types for HomeFit API responses

export interface Coordinates {
  lat: number;
  lon: number;
}

/** Top driver item for Status Signal tooltip. */
export interface StatusSignalTopDriver {
  label: string;
  score: number;
}

/** Status Signal breakdown (archetype, label, insight, top drivers, radius note). */
export interface StatusSignalBreakdown {
  archetype?: string;
  status_label?: string;
  status_insight?: string;
  top_drivers?: StatusSignalTopDriver[];
  analysis_radius_note?: string | null;
  [key: string]: unknown;
}

export interface LocationInfo {
  city: string;
  state: string;
  zip: string;
}

export interface PillarBreakdown {
  [key: string]: any;
}

export interface PillarSummary {
  [key: string]: any;
}

export interface DataQuality {
  confidence?: number;
  quality_tier?: string;
  fallback_used?: boolean;
  /** Human-readable reason when fallback was used (for tooltips). */
  fallback_reason?: string;
  data_sources?: string[];
  [key: string]: any;
}

export interface AreaClassification {
  area_type?: string;
  form_context?: string;
  metro_name?: string;
  [key: string]: any;
}

export interface LivabilityPillar {
  score: number;
  base_score?: number;
  selected_job_categories?: string[];
  job_category_overlays?: any;
  weight: number;
  importance_level?: 'None' | 'Low' | 'Medium' | 'High' | null;
  contribution: number;
  breakdown?: PillarBreakdown;
  summary?: PillarSummary;
  details?: any;
  confidence: number;
  data_quality: DataQuality;
  area_classification?: AreaClassification;
  /** Set when pillar execution failed; client should show low confidence and "Rerun" prompt. */
  error?: string;
  /** Source of truth for UI state: 'success' | 'fallback' | 'failed'. */
  status?: 'success' | 'fallback' | 'failed';
}

export interface LivabilityPillars {
  active_outdoors: LivabilityPillar;
  built_beauty: LivabilityPillar;
  natural_beauty: LivabilityPillar;
  neighborhood_amenities: LivabilityPillar;
  air_travel_access: LivabilityPillar;
  public_transit_access: LivabilityPillar;
  healthcare_access: LivabilityPillar;
  // Defensive: some deployments may not include this pillar yet.
  economic_security?: LivabilityPillar;
  quality_education: LivabilityPillar;
  housing_value: LivabilityPillar;
  /** Climate & Flood Risk (Phase 1A); may be absent in older deployments. */
  climate_risk?: LivabilityPillar;
  /** Social Fabric (Phase 2B); may be absent in older deployments. */
  social_fabric?: LivabilityPillar;
  /** Demographic diversity (entropy); may be absent in older deployments. */
  diversity?: LivabilityPillar;
}

export interface OverallConfidence {
  average_confidence: number;
  pillars_using_fallback: number;
  fallback_percentage: number;
  quality_tier_distribution: Record<string, number>;
  overall_quality: string;
}

export interface DataQualitySummary {
  data_sources_used: string[];
  area_classification: {
    area_type?: string;
    form_context?: string;
    metro_name?: string;
    [key: string]: any;
  };
  total_pillars: number;
  data_completeness: string;
}

export interface Metadata {
  version: string;
  architecture: string;
  note: string;
  test_mode: boolean;
  cache_hit?: boolean;
  cache_timestamp?: number;
  /**
   * Optional: persisted client search configuration used when the score was generated.
   * Stored so saved scores can restore the user's original preferences.
   */
  saved_search_options?: import('@/components/SearchOptions').SearchOptions | null;
  /** Allow forward-compatible metadata keys without breaking the type. */
  [key: string]: unknown;
}

export interface ScoreResponse {
  input: string;
  coordinates: Coordinates;
  location_info: LocationInfo;
  livability_pillars: LivabilityPillars;
  /** Short factual summary (2–4 sentences) from pillar data; template-based, no LLM. */
  place_summary?: string;
  total_score: number;
  /** Longevity Index: fixed blend of social_fabric, neighborhood_amenities, active_outdoors, natural_beauty, climate_risk, quality_education. Separate from total_score. */
  longevity_index?: number;
  /** Per-pillar contribution to longevity_index (same six pillars). */
  longevity_index_contributions?: Record<string, number>;
  /** Status Signal: wealth, home cost, education mix, occupation, luxury POI presence (OSM + fallback). Needs four pillars. */
  status_signal?: number;
  /** Detailed component breakdown for Status Signal (archetype, status_label, status_insight, top_drivers, analysis_radius_note). */
  status_signal_breakdown?: StatusSignalBreakdown;
  /** Happiness Index: commute (35%), social fabric (30%), housing value (20%), natural beauty (15%); renormalized if missing. Not a pillar. */
  happiness_index?: number;
  happiness_index_breakdown?: Record<string, unknown>;
  token_allocation: Record<string, number>;
  allocation_type: string;
  overall_confidence: OverallConfidence;
  data_quality_summary: DataQualitySummary;
  metadata: Metadata;
}

export interface ScoreRequestParams {
  location: string;
  tokens?: string;
  priorities?: string;
  job_categories?: string;
  include_chains?: boolean;
  enable_schools?: boolean;
  /** Request only these pillars (e.g. "economic_security"); backend param "only". */
  only?: string;
  /** Natural Beauty preference: JSON array of 1–2 of mountains, ocean, lakes_rivers, canopy. */
  natural_beauty_preference?: string;
  /** Built Beauty character: historic | contemporary | no_preference. */
  built_character_preference?: string;
  /** Built Beauty density: spread_out_residential | walkable_residential | dense_urban_living. */
  built_density_preference?: string;
  /** When set, backend uses these coordinates instead of geocoding location (ensures refresh uses same point). */
  lat?: number;
  lon?: number;
}

/** Response from GET /geocode — used to show map before scoring. */
export interface GeocodeResult {
  lat: number;
  lon: number;
  city: string;
  state: string;
  zip_code: string;
  display_name: string;
}

/** Payload for POST /score/recompute_composites — recompute indices from existing pillar data. */
export interface RecomputePayload {
  livability_pillars: LivabilityPillars;
  location_info?: LocationInfo | Record<string, unknown>;
  coordinates?: Coordinates | { lat: number; lon: number };
  token_allocation?: Record<string, number>;
}

/** Response from POST /score/recompute_composites. */
export interface RecomputeResponse {
  longevity_index: number | null;
  longevity_index_contributions: Record<string, number> | null;
  status_signal: number | null;
  status_signal_breakdown: StatusSignalBreakdown | null;
  happiness_index: number | null;
  happiness_index_breakdown: Record<string, unknown> | null;
  /** Backend composite index spec versions (longevity / status_signal / happiness). */
  indices_version?: Record<string, string>;
}
