// TypeScript types for HomeFit API responses

export interface Coordinates {
  lat: number;
  lon: number;
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
  weight: number;
  contribution: number;
  breakdown?: PillarBreakdown;
  summary?: PillarSummary;
  details?: any;
  confidence: number;
  data_quality: DataQuality;
  area_classification?: AreaClassification;
}

export interface LivabilityPillars {
  active_outdoors: LivabilityPillar;
  built_beauty: LivabilityPillar;
  natural_beauty: LivabilityPillar;
  neighborhood_amenities: LivabilityPillar;
  air_travel_access: LivabilityPillar;
  public_transit_access: LivabilityPillar;
  healthcare_access: LivabilityPillar;
  quality_education: LivabilityPillar;
  housing_value: LivabilityPillar;
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
}

export interface ScoreResponse {
  input: string;
  coordinates: Coordinates;
  location_info: LocationInfo;
  livability_pillars: LivabilityPillars;
  total_score: number;
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
  include_chains?: boolean;
  enable_schools?: boolean;
}
