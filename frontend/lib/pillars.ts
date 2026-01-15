export type PillarKey =
  | 'natural_beauty'
  | 'built_beauty'
  | 'neighborhood_amenities'
  | 'active_outdoors'
  | 'healthcare_access'
  | 'public_transit_access'
  | 'air_travel_access'
  | 'quality_education'
  | 'housing_value'

export const PILLAR_META: Record<
  PillarKey,
  { icon: string; name: string; description: string }
> = {
  natural_beauty: {
    icon: '🌳',
    name: 'Natural Beauty',
    description: 'Tree canopy, water, and dramatic terrain nearby',
  },
  built_beauty: {
    icon: '🏛️',
    name: 'Built Beauty',
    description: 'Architectural character, variety, and placemaking details',
  },
  neighborhood_amenities: {
    icon: '🏘️',
    name: 'Neighborhood Amenities',
    description: 'Walkable essentials, variety, and neighborhood vibrancy',
  },
  active_outdoors: {
    icon: '🏃',
    name: 'Active Outdoors',
    description: 'Parks, trails, camping, and waterfront recreation',
  },
  healthcare_access: {
    icon: '🏥',
    name: 'Healthcare Access',
    description: 'Hospitals, primary care, specialists, and pharmacies',
  },
  public_transit_access: {
    icon: '🚇',
    name: 'Public Transit Access',
    description: 'Rail/bus service, multimodal coverage, and commute options',
  },
  air_travel_access: {
    icon: '✈️',
    name: 'Air Travel Access',
    description: 'Distance to airports and multiple airport options',
  },
  quality_education: {
    icon: '🏫',
    name: 'Schools',
    description: 'K-12 quality with early education and nearby colleges',
  },
  housing_value: {
    icon: '💰',
    name: 'Housing Value',
    description: 'Affordability and space/value for typical housing',
  },
}

export function getScoreBadgeClass(score: number): string {
  if (score >= 80) return 'hf-score-badge hf-score-badge--green'
  if (score >= 60) return 'hf-score-badge hf-score-badge--blue'
  if (score >= 40) return 'hf-score-badge hf-score-badge--yellow'
  return 'hf-score-badge hf-score-badge--red'
}

