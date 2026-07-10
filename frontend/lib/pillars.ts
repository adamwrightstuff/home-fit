export type PillarKey =
  | 'neighborhood_beauty'
  | 'natural_beauty'
  | 'built_environment'
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
  | 'community_safety'
  | 'political_lean'

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
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'housing_value',
  'community_safety',
  'political_lean',
]
export const LONGEVITY_PILLAR_KEYS: ReadonlySet<PillarKey> = new Set<PillarKey>([
  'social_fabric',
  'active_outdoors',
  'neighborhood_amenities',
  'natural_beauty',
  'climate_risk',
  'quality_education',
])

/** Pillars that feed the Happiness Index (tag dot on pillar cards). */
export const HAPPINESS_PILLAR_KEYS: ReadonlySet<PillarKey> = new Set<PillarKey>([
  'public_transit_access',
  'social_fabric',
  'housing_value',
  'natural_beauty',
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
  /** Full version for modal. */
  full:
    "Predicts long-term health outcomes based on Blue Zone–style research. Same formula for everyone — ignores your Trovamo weights.",
  /** Short version for subtitle or card label. */
  short:
    'Six Blue Zone–style pillars (social fabric, amenities, outdoors, nature, climate, schools) — same formula for everyone.',
  /** One-line tooltip next to the score. */
  tooltip:
    'Predicts long-term health outcomes based on Blue Zone–style research. Same formula for everyone — ignores your Trovamo weights.',
  /** Key distinction to communicate. */
  distinction:
    'Trovamo = right for you. Longevity = right for your health over time.',
} as const

/** Copy for Trovamo Score UX: tooltip, subtitle, full modal, and callout distinction. */
export const HOMEFIT_COPY = {
  /** Full body for modal — Results, Saved, Public (13 active pillars). */
  full:
    'A composite of all 13 pillars, weighted equally by default. Adjust weights to personalize.',
  /** Full body for modal — Explorer catalog (15 pillars including Community Safety + Political Vibe). */
  fullCatalog:
    'A composite of all 15 pillars, weighted equally by default. Adjust weights to personalize.',
  /** Subtitle under "Trovamo Score" label. */
  subtitle:
    'How well this place meets your lifestyle needs based on your personalized preferences.',
  /** One-line tooltip for ? button. */
  tooltip:
    'A composite of all 13 pillars, weighted equally by default. Adjust weights to personalize.',
  /** Callout in modal. */
  distinction:
    'Trovamo = right for you. Longevity = right for your health over time.',
} as const

/** Copy for Archetype index UX: tooltip and modal. */
export const STATUS_SIGNAL_COPY = {
  tooltip:
    'Every neighborhood has a social character — shaped by who lives there, what they earn, and what they do. Archetype captures it using income, education, occupation, and housing data.',
  full:
    'Every neighborhood has a social character — shaped by who lives there, what they earn, and what they do. Archetype captures it using income, education, occupation, and housing data.',
} as const

/** Copy for Happiness Index UX: tooltip and modal. */
export const HAPPINESS_INDEX_COPY = {
  /** One-line tooltip next to the score. */
  tooltip:
    'Captures day-to-day livability, weighted toward commute and social connection.',
  /** Full version for modal. */
  full:
    'Captures day-to-day livability, weighted toward commute and social connection.',
  /** Short version for subtitle or card label. */
  short:
    'Commute, social fabric, housing space-for-price, nature, and built beauty — fixed weights when all five are available.',
} as const

/** Copy for Trajectory UX: tooltip and per-state modal copy. */
export const TRAJECTORY_COPY = {
  tooltip:
    'How a neighborhood\'s market has moved over the past three years — based on home values and price momentum.',
  states: {
    Arrived:
      "This neighborhood's premium is established and holding. Wealth signals are high and the market isn't in active flux — you're buying stability and a known identity. These places rarely transform quickly, which is the point. Expect to pay full price for what you see.",
    'Up-and-Coming':
      "Strong appreciation signal over the past three years. The neighborhood is being discovered — wealth and status indicators are climbing and prices are following. You're buying in front of the premium, not after it. Identity may still be in flux, which carries both upside and uncertainty.",
    Stable:
      "No significant appreciation or depreciation signal. The neighborhood has a consistent character without active transformation. This isn't a negative — many desirable places are simply stable. What you see is what you'll get.",
    Cooling:
      'Prices have softened after a prior peak. The neighborhood may be over-supplied, losing a demand driver, or seeing early demographic shift. Not a crisis, but worth tracking recent comps closely before committing. The identity is intact; the market is less certain.',
    Declining:
      'Consistent price decline over three or more years with no recovery signal. Underlying wealth or stability indicators are also weakening. This doesn\'t disqualify the neighborhood — but the market is telling a clear story. Approach with eyes open and a longer investment horizon.',
  } as Record<string, string>,
  tableRows: [
    { label: 'Arrived', desc: 'Premium locked in, stable' },
    { label: 'Up-and-coming', desc: 'Prices rising, identity in flux' },
    { label: 'Stable', desc: 'No strong momentum either way' },
    { label: 'Cooling', desc: 'Premium softening' },
    { label: 'Declining', desc: 'Sustained downward pressure' },
  ] as { label: string; desc: string }[],
  source: 'Based on 3-year home value trend data.',
}

/** Comma-separated pillar names required to compute the archetype index (for only= param). */
export const STATUS_SIGNAL_ONLY_PILLARS =
  'housing_value,social_fabric,economic_security,neighborhood_amenities,diversity'

export function isLongevityPillar(key: PillarKey): boolean {
  return LONGEVITY_PILLAR_KEYS.has(key)
}

export function isHappinessPillar(key: PillarKey): boolean {
  return HAPPINESS_PILLAR_KEYS.has(key)
}

export const PILLAR_META: Record<
  PillarKey,
  { icon: string; name: string; description: string }
> = {
  neighborhood_beauty: {
    icon: '🏡',
    name: 'Neighborhood Beauty',
    description:
      'Architecture and landscape together — thoughtfully designed streets and buildings paired with trees, water, and scenic character, weighted by how dense or built-up the area is',
  },
  natural_beauty: {
    icon: '🌿',
    name: 'Natural Beauty',
    description:
      'Trees, water, topography, and scenic landscape — how much nature is woven into the place, from ocean views to urban tree canopy.',
  },
  built_environment: {
    icon: '🏙️',
    name: 'Built Environment',
    description:
      'The type of neighborhood you want to live in — from walkable urban core to quiet suburb or rural town. Match score based on area type.',
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
  community_safety: {
    icon: '🛡️',
    name: 'Community Safety',
    description:
      'Local crime rates and safety conditions — how secure the area feels day-to-day based on reported incidents.',
  },
  political_lean: {
    icon: '🗳️',
    name: 'Political Vibe',
    description:
      'How the area has voted in the last two presidential elections — for those who prefer to live among people with similar political values.',
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
  neighborhood_beauty:
    'Combines architecture and landscape: thoughtfully designed streets and buildings create a sense of place and belonging, while access to trees, water, and scenic landscapes is linked to lower stress and better mental health. The two are blended based on how dense or built-up the area is — denser places weight built character more, leafier ones weight nature more.',
  natural_beauty:
    'Trees, water, topography, and scenic landscape — how much nature is woven into the place, from ocean views to urban tree canopy. Adjust the scenery preference to weight your preferred landscape type.',
  built_environment:
    'How well the neighborhood type matches what you are looking for — urban core, urban neighborhood, suburban, exurban, or rural. Score reflects how closely the area type aligns with your preference.',
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
  community_safety:
    'Feeling safe at home and in your neighborhood affects daily wellbeing, children\'s freedom to play outside, and long-term quality of life. This score is based on reported local crime rates relative to comparable areas.',
  political_lean:
    'Some people feel more at home in a community that shares their political values. This score is based on 2020 and 2024 presidential election results at the precinct level — weighted by your declared preference.',
}

export function getScoreBadgeClass(score: number): string {
  if (score >= 80) return 'hf-score-badge hf-score-badge--green'
  if (score >= 60) return 'hf-score-badge hf-score-badge--blue'
  if (score >= 40) return 'hf-score-badge hf-score-badge--yellow'
  return 'hf-score-badge hf-score-badge--red'
}
