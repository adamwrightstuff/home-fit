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
  | 'climate_risk'

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
  climate_risk: {
    icon: '🌡️',
    name: 'Climate & Flood Risk',
    description:
      'Lower exposure to heat, flooding, and poor air quality—so the place stays livable for decades',
  },
}

// ---------------------------------------------------------------------------
// Phase 1B: Score bands (PRD 5.5)
// ---------------------------------------------------------------------------
export const SCORE_BANDS = [
  { min: 80, max: 100, label: 'Excellent', color: '#4A9E6B' },
  { min: 60, max: 79, label: 'Good', color: '#7AB87A' },
  { min: 40, max: 59, label: 'Fair', color: '#C8B84A' },
  { min: 20, max: 39, label: 'Needs Work', color: '#C8854A' },
  { min: 0, max: 19, label: 'Poor', color: '#C85A5A' },
] as const

export function getScoreBand(score: number): { label: string; color: string } {
  const band = SCORE_BANDS.find((b) => score >= b.min && score <= b.max)
  return band
    ? { label: band.label, color: band.color }
    : { label: '—', color: '#888' }
}

export function getScoreBandLabel(score: number): string {
  return getScoreBand(score).label
}

export function getScoreBandColor(score: number): string {
  return getScoreBand(score).color
}

// ---------------------------------------------------------------------------
// Phase 1B: Long descriptions ("why this matters") for expand/tooltip
// ---------------------------------------------------------------------------
export const PILLAR_LONG_DESCRIPTIONS: Record<PillarKey, string> = {
  natural_beauty:
    'Access to trees, water, and scenic landscapes is linked to lower stress and better mental health. Neighborhoods with strong canopy and natural features tend to support walking and outdoor time, which supports long-term wellbeing.',
  built_beauty:
    'Thoughtfully designed streets and buildings create a sense of place and belonging. Diverse, human-scale architecture is associated with higher satisfaction and walkability, which in turn supports health and social connection.',
  neighborhood_amenities:
    'Being able to walk to cafés, groceries, and daily needs reduces car dependence and encourages routine activity. Neighborhoods with a mix of local businesses tend to foster social interaction and a stronger sense of community.',
  active_outdoors:
    'Regular access to parks, trails, and waterfront supports physical activity and time in nature. Research links these opportunities to better cardiovascular health, mental wellbeing, and longevity.',
  healthcare_access:
    'Proximity to hospitals, clinics, and pharmacies improves outcomes when care is needed. Good access reduces delay in emergencies and makes preventive care and chronic disease management easier to maintain.',
  public_transit_access:
    'Reliable transit expands options for work, education, and social life without depending on a car. It can reduce commute stress, support physical activity (walking to stops), and improve financial stability by lowering transport costs.',
  air_travel_access:
    'Reasonable access to airports makes it easier to stay connected with family, travel for work, and take trips. It supports social bonds and life satisfaction, especially for those who value mobility.',
  economic_security:
    'Local job variety, wage levels, and business dynamism affect financial security and opportunity. Strong, diversified economies tend to offer better job matches and resilience during downturns.',
  quality_education:
    'Strong local schools support child development and family satisfaction. Access to good K–12 and nearby higher education is associated with long-term outcomes and neighborhood stability.',
  housing_value:
    'Affordability relative to income and space per dollar affect financial stress and quality of life. Places that offer more space and value for the money can support wellbeing and long-term stability.',
  climate_risk:
    'Exposure to flooding, extreme heat, and poor air quality can affect safety, insurance costs, and health over time. Lower risk supports long-term livability and peace of mind.',
}

export function getScoreBadgeClass(score: number): string {
  if (score >= 80) return 'hf-score-badge hf-score-badge--green'
  if (score >= 60) return 'hf-score-badge hf-score-badge--blue'
  if (score >= 40) return 'hf-score-badge hf-score-badge--yellow'
  return 'hf-score-badge hf-score-badge--red'
}
