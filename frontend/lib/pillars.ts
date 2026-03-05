export type PillarKey =
  | 'natural_beauty'
  | 'built_beauty'
  | 'access_to_nature'
  | 'neighborhood_amenities'
  | 'active_outdoors'
  | 'healthcare_access'
  | 'public_transit_access'
  | 'air_travel_access'
  | 'economic_security'
  | 'quality_education'
  | 'housing_value'
  | 'climate_risk'
  | 'social_fabric'

/** Pillars that contribute to the Longevity Index (fixed weighted blend). */
export const LONGEVITY_PILLAR_KEYS: ReadonlySet<PillarKey> = new Set<PillarKey>([
  'social_fabric',
  'active_outdoors',
  'neighborhood_amenities',
  'natural_beauty',
  'climate_risk',
  'quality_education',
])

/** Copy for Longevity Score UX: tooltip, short subtitle, full modal, and key distinction. */
export const LONGEVITY_COPY = {
  /** Full version for tooltip/modal. */
  full:
    "The Longevity Score measures how well a place supports a long, healthy life — not just whether it fits your preferences today. It's built on six factors that research links to lifespan and wellbeing: social connectedness, opportunities for natural movement, walkable daily life, restorative natural environments, climate stability, and cognitive engagement. The weights come from Blue Zone research — the places in the world where people live longest share these traits in common. A high Longevity Score means the place itself is working in your favor over time.",
  /** Short version for subtitle or card label. */
  short:
    'How well this place supports a long, healthy life — based on Blue Zone research.',
  /** One-line tooltip next to the score. */
  tooltip:
    'Measures long-term livability across social fabric, movement, nature, and climate — independent of your personal priorities.',
  /** Key distinction to communicate. */
  distinction:
    'HomeFit = right for you. Longevity = right for your health over time.',
} as const

/** Copy for HomeFit Score UX: tooltip, subtitle, full modal, and callout distinction. */
export const HOMEFIT_COPY = {
  /** Full body for modal. */
  full:
    "The HomeFit Score measures how well a place matches your priorities — not anyone else's. Before scoring, you tell us what matters to you: how much you care about schools, walkability, natural beauty, transit, and more. The score is weighted accordingly, so two people can look at the same place and get completely different HomeFit scores based on their lives.",
  /** Subtitle under "HomeFit Score" label. */
  subtitle:
    'How well this place meets your lifestyle needs based on your personalized preferences.',
  /** One-line tooltip for ? button. */
  tooltip:
    'How well this place meets your lifestyle needs based on your personalized preferences.',
  /** Callout in modal. */
  distinction:
    'HomeFit = right for you. Longevity = right for your health over time.',
} as const

export function isLongevityPillar(key: PillarKey): boolean {
  return LONGEVITY_PILLAR_KEYS.has(key)
}

export const PILLAR_META: Record<
  PillarKey,
  { icon: string; name: string; description: string }
> = {
  natural_beauty: {
    icon: '🌳',
    name: 'Natural Beauty',
    description:
      'The natural landscape around you — mountains, water, or greenery — scored for what matters to you',
  },
  built_beauty: {
    icon: '🏛️',
    name: 'Built Beauty',
    description:
      "Architecture and streetscapes that feel thoughtfully designed—not cookie-cutter, but crafted with character",
  },
  access_to_nature: {
    icon: '🌿',
    name: 'Access to Nature',
    description:
      'What it feels like when you step outside—tree-lined streets, nearby parks, water, and hills for everyday downshift',
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
  social_fabric: {
    icon: '🤝',
    name: 'Social Fabric',
    description:
      'Neighbors, civic spaces, and local rootedness that support belonging—not just shops but libraries, community centers, and long-term residents.',
  },
}

// ---------------------------------------------------------------------------
// Phase 1B: Score bands (PRD 5.5) — Score Badge acceptance criteria
// 85–100: Excellent | 70–84: Good | 45–69: Fair | 0–44: Low
// ---------------------------------------------------------------------------
export const SCORE_BANDS = [
  { min: 85, max: 100, label: 'Excellent', color: '#4A9E6B' },
  { min: 70, max: 84, label: 'Good', color: '#7AB87A' },
  { min: 45, max: 69, label: 'Fair', color: '#C8B84A' },
  { min: 0, max: 44, label: 'Low', color: '#C8854A' },
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
  access_to_nature:
    'Living near trees, parks, water, and hills supports mental restoration and a sense of escape from the built environment. This pillar measures how quickly you can be in nature from your front door—not recreation, but everyday exposure.',
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
  social_fabric:
    'A strong social fabric means people know their neighbors, share civic spaces, and have places to gather that are not tied to spending money. Stable residency and civic third places—like libraries, community centers, and town halls—are linked to higher trust, informal support, and long-term wellbeing.',
}

export function getScoreBadgeClass(score: number): string {
  if (score >= 80) return 'hf-score-badge hf-score-badge--green'
  if (score >= 60) return 'hf-score-badge hf-score-badge--blue'
  if (score >= 40) return 'hf-score-badge hf-score-badge--yellow'
  return 'hf-score-badge hf-score-badge--red'
}
