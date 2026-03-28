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
  | 'social_fabric'
  | 'diversity'

/** Display order for pillars on HomeFit pillar screen and related UIs. */
export const PILLAR_ORDER: PillarKey[] = [
  'quality_education',
  'neighborhood_amenities',
  'economic_security',
  'climate_risk',
  'active_outdoors',
  'natural_beauty',
  'diversity',
  'social_fabric',
  'built_beauty',
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'housing_value',
]
export const LONGEVITY_PILLAR_KEYS: ReadonlySet<PillarKey> = new Set<PillarKey>([
  'social_fabric',
  'active_outdoors',
  'neighborhood_amenities',
  'natural_beauty',
  'climate_risk',
  'quality_education',
])

/** Weights for Longevity Index (must match backend LONGEVITY_INDEX_WEIGHTS). */
export const LONGEVITY_INDEX_WEIGHTS: Record<string, number> = {
  social_fabric: 40,
  neighborhood_amenities: 25,
  active_outdoors: 15,
  natural_beauty: 10,
  climate_risk: 8,
  quality_education: 2,
}

/**
 * Compute Longevity Index (0–100) from pillar scores using fixed longevity weights.
 * Uses only longevity pillars that have a valid score (excludes failed runs); renormalizes weights over that subset.
 * Returns null if no longevity pillar has a valid score.
 */
export function computeLongevityIndex(
  pillarScores: Record<string, { score?: number; failed?: boolean }>
): number | null {
  const eligible = (Object.keys(LONGEVITY_INDEX_WEIGHTS) as PillarKey[]).filter((p) => {
    const entry = pillarScores[p]
    if (!entry) return false
    if (entry.failed) return false
    const s = entry.score
    return typeof s === 'number' && Number.isFinite(s)
  })
  if (eligible.length === 0) return null
  const totalWeight = eligible.reduce((sum, p) => sum + LONGEVITY_INDEX_WEIGHTS[p], 0)
  if (totalWeight <= 0) return null
  let total = 0
  for (const p of eligible) {
    const score = pillarScores[p]!.score!
    total += score * (LONGEVITY_INDEX_WEIGHTS[p] / totalWeight)
  }
  return Math.round(total * 100) / 100
}

/** API `only=` list includes every longevity pillar → server returns a meaningful longevity_index. */
export function allLongevityPillarsInOnlyKeys(onlyKeys: string[]): boolean {
  const set = new Set(onlyKeys)
  return (Object.keys(LONGEVITY_INDEX_WEIGHTS) as PillarKey[]).every((k) => set.has(k))
}

/** Longevity index from merged livability_pillars (saved/API shape). */
export function longevityIndexFromLivabilityPillars(
  pillars: Record<string, { score?: number; status?: string; error?: string } | undefined>
): number | null {
  const pillarScores: Record<string, { score?: number; failed?: boolean }> = {}
  for (const k of Object.keys(LONGEVITY_INDEX_WEIGHTS) as PillarKey[]) {
    const p = pillars[k]
    if (!p || typeof p.score !== 'number' || !Number.isFinite(p.score)) continue
    pillarScores[k] = {
      score: p.score,
      failed: Boolean(p.error) || p.status === 'failed',
    }
  }
  return computeLongevityIndex(pillarScores)
}

/** Copy for Longevity Score UX: tooltip, short subtitle, full modal, and key distinction. */
export const LONGEVITY_COPY = {
  /** Full version for tooltip/modal. */
  full:
    "The Longevity Score measures how well a place supports a long, healthy life — not whether it matches your priorities today. It's a fixed blend of six pillars (same weights for everyone): Social Fabric, Neighborhood Amenities (walkable daily life), Active Outdoors, Natural Beauty, Climate Risk, and Schools / Quality Education. Those weights follow Blue Zone–style research on where people live longest. A high score means the place is structurally working in your favor for health over time — independent of how you weighted pillars for your HomeFit Score.",
  /** Short version for subtitle or card label. */
  short:
    'Six Blue Zone–style pillars (social fabric, amenities, outdoors, nature, climate, schools) — same formula for everyone.',
  /** One-line tooltip next to the score. */
  tooltip:
    'Social fabric, daily amenities, active outdoors, natural beauty, climate risk, and schools — fixed Blue Zone–style blend; ignores your HomeFit pillar weights.',
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

/** Copy for Status Signal UX: tooltip and modal. */
export const STATUS_SIGNAL_COPY = {
  tooltip:
    'Wealth, housing cost vs peers, education, occupation, and upscale nearby venues (mapped POIs; name fallback if needed) — 0–100 vs local baselines after Housing, Social Fabric, Economic Security, and Amenities; not your HomeFit weights. The badge names a profile type, not a rank above the score.',
  full:
    'Status Signal is a 0–100 composite after scoring: household wealth (income vs local baselines), how expensive housing is for the area, education mix (emphasis on graduate degrees, plus bachelor’s and self-employment), occupation mix (e.g. finance, creative, white-collar share), and “luxury presence” from mapped POI types near you (offices, recreation, arts, retail, etc.) — with a fallback to name-based matching if map data isn’t available. It needs Housing, Social Fabric, Economic Security, and Neighborhood Amenities; refresh by running just those four pillars.',
} as const

/** Copy for Happiness Index UX: tooltip and modal. */
export const HAPPINESS_INDEX_COPY = {
  /** One-line tooltip next to the score. */
  tooltip:
    'Commute ease (35%), social fabric (30%), housing value for space (20%), natural beauty (15%) — weights rebalance if a piece is missing.',
  /** Full version for modal. */
  full:
    'Happiness Index blends four ingredients already in your score: easier commutes (public transit pillar), stronger social fabric (neighbors, civic life), better housing value for space (price-to-space), and more natural beauty (green and blue space). Default weights are 35% / 30% / 20% / 15%; if we’re missing data for one piece, the others are scaled so the index still sums to a full 0–100.',
  /** Short version for subtitle or card label. */
  short:
    'Commute, social fabric, housing space-for-price, and nature — fixed weights when all four are available.',
} as const

/** Comma-separated pillar names required to compute Status Signal (for only= param). */
export const STATUS_SIGNAL_ONLY_PILLARS =
  'housing_value,social_fabric,economic_security,neighborhood_amenities,diversity'

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
  neighborhood_amenities: {
    icon: '🛒',
    name: 'Daily Amenities',
    description:
      'A walkable town center with a variety of daily amenities — from coffee and groceries to shops and restaurants — within reach.',
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
      'The strength of the local job market for your profession—or the health of the local economy if you work remotely.',
  },
  quality_education: {
    icon: '🏫',
    name: 'Schools',
    description: 'Strong local schools that set kids up for success—from early education through high school and beyond',
  },
  housing_value: {
    icon: '🏠',
    name: 'Home Price to Space',
    description:
      "More space and quality for your money — where housing costs make sense for what you're getting",
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
  diversity: {
    icon: '🌐',
    name: 'Diversity',
    description:
      'Race, income, and age mix in the neighborhood—entropy-based measure of how varied the community is.',
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

/** Badge background tint (band color at ~15% opacity) for spec Section 1 "Badge color maps to band". */
export function getScoreBandBackground(score: number): string {
  const hex = getScoreBandColor(score)
  const n = parseInt(hex.slice(1), 16)
  const r = (n >> 16) & 0xff
  const g = (n >> 8) & 0xff
  const b = n & 0xff
  return `rgba(${r}, ${g}, ${b}, 0.15)`
}

// ---------------------------------------------------------------------------
// Pillar data quality / failure state (derived from status + quality_tier)
// ---------------------------------------------------------------------------
export type PillarFailureType = 'none' | 'incomplete' | 'fallback' | 'execution_error'

export function getPillarFailureType(pillar: {
  status?: string
  error?: string
  data_quality?: { quality_tier?: string }
}): PillarFailureType {
  const status = pillar.status ?? (pillar.error ? 'failed' : 'success')
  const tier = pillar.data_quality?.quality_tier ?? 'fair'
  if (status === 'failed') return 'execution_error'
  if (status === 'fallback') return 'fallback'
  if (status === 'success') {
    if (tier === 'poor' || tier === 'very_poor') return 'incomplete'
    return 'none'
  }
  return 'none'
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
    'Local job market strength for your profession, or overall economic health if you work remotely. Job category focus personalizes density, ecosystem, and resilience.',
  quality_education:
    'Strong local schools support child development and family satisfaction. Access to good K–12 and nearby higher education is associated with long-term outcomes and neighborhood stability.',
  housing_value:
    'Affordability relative to income and space per dollar affect financial stress and quality of life. Places that offer more space and value for the money can support wellbeing and long-term stability.',
  climate_risk:
    'Exposure to flooding, extreme heat, and poor air quality can affect safety, insurance costs, and health over time. Lower risk supports long-term livability and peace of mind.',
  social_fabric:
    'A strong social fabric means people know their neighbors, share civic spaces, and have places to gather that are not tied to spending money. Stable residency and civic third places—like libraries, community centers, and town halls—are linked to higher trust, informal support, and long-term wellbeing.',
  diversity:
    'Neighborhood diversity in race, income, and age reflects exposure to different life experiences and can support vibrant daily life. This score uses Census distributions (not architectural variety).',
}

export function getScoreBadgeClass(score: number): string {
  if (score >= 80) return 'hf-score-badge hf-score-badge--green'
  if (score >= 60) return 'hf-score-badge hf-score-badge--blue'
  if (score >= 40) return 'hf-score-badge hf-score-badge--yellow'
  return 'hf-score-badge hf-score-badge--red'
}
