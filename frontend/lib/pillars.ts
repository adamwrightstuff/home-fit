export type PillarKey =
  | 'natural_beauty'
  | 'built_beauty'
  | 'neighborhood_amenities'
  | 'active_outdoors'
  | 'healthcare_access'
  | 'public_transit_access'
  | 'air_travel_access'
  | 'economic_security'
  | 'quality_education'
  | 'housing_value'

export const PILLAR_META: Record<
  PillarKey,
  { icon: string; name: string; description: string }
> = {
  natural_beauty: {
    icon: '🌳',
    name: 'Natural Beauty',
    description:
      'Tree-lined streets, nearby water, and access to dramatic landscapes—from urban canopy to mountain views',
  },
  built_beauty: {
    icon: '🏛️',
    name: 'Built Beauty',
    description:
      "Architecture and streetscapes that feel thoughtfully designed—not cookie-cutter, but crafted with character",
  },
  neighborhood_amenities: {
    icon: '🏘️',
    name: 'Neighborhood Amenities',
    description:
      "Walkable variety and neighborhood character—where you have choices for coffee, groceries, and daily needs without driving",
  },
  active_outdoors: {
    icon: '🏃',
    name: 'Active Outdoors',
    description: 'Easy access to trails, parks, and waterfront recreation—for weekend adventures or after-work runs',
  },
  healthcare_access: {
    icon: '🏥',
    name: 'Healthcare Access',
    description:
      "Quality medical care nearby when you need it—hospitals, doctors, specialists, and pharmacies you can count on",
  },
  public_transit_access: {
    icon: '🚇',
    name: 'Public Transit Access',
    description: "Reliable transit options that get you where you're going—so driving isn't your only choice",
  },
  air_travel_access: {
    icon: '✈️',
    name: 'Air Travel Access',
    description: 'Good airports within reasonable reach—making trips to see family or explore new places less of a hassle',
  },
  economic_security: {
    icon: '📈',
    name: 'Economic Opportunity',
    description:
      'Local economic opportunity and resilience—job market health, earnings vs. cost, business dynamism, and diversification',
  },
  quality_education: {
    icon: '🏫',
    name: 'Schools',
    description: 'Strong local schools that set kids up for success—from early education through high school and beyond',
  },
  housing_value: {
    icon: '💰',
    name: 'Housing Value',
    description: "More space and quality for your money—where housing costs make sense for what you're getting",
  },
}

export function getScoreBadgeClass(score: number): string {
  if (score >= 80) return 'hf-score-badge hf-score-badge--green'
  if (score >= 60) return 'hf-score-badge hf-score-badge--blue'
  if (score >= 40) return 'hf-score-badge hf-score-badge--yellow'
  return 'hf-score-badge hf-score-badge--red'
}

