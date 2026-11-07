export type PriorityLevel = 'None' | 'Low' | 'Medium' | 'High'

interface PillarPriorities {
  active_outdoors: PriorityLevel
  natural_beauty: PriorityLevel
  neighborhood_amenities: PriorityLevel
  air_travel_access: PriorityLevel
  public_transit_access: PriorityLevel
  healthcare_access: PriorityLevel
  economic_opportunity: PriorityLevel
  quality_education: PriorityLevel
  housing_value: PriorityLevel
  climate_risk: PriorityLevel
  social_fabric: PriorityLevel
  diversity: PriorityLevel
  community_safety: PriorityLevel
  political_lean: PriorityLevel
  /** Opt-in, catalog-explorer only -- not one of the 12 research-backed pillars (see CLAUDE.md).
   * Only affects HomeFit total when a work hub is selected; otherwise inert like political_lean. */
  commute_time?: PriorityLevel
  /** Opt-in, catalog-explorer only -- see lib/reweight.ts. Only affects HomeFit total once at
   * least one person has been added via PeopleYouKnowPicker; otherwise inert. */
  social_connection?: PriorityLevel
}

interface SearchOptions {
  priorities: PillarPriorities
  include_chains: boolean
  enable_schools: boolean
  job_categories: string[]
  /** Natural Beauty preference from quiz: 1–2 of mountains, ocean, lakes_rivers, canopy; null = no preference. */
  natural_beauty_preference?: string[] | null
  /** Diversity: which mix dimensions to emphasize in the headline (race, income, age). null = average all available. */
  diversity_preference?: string[] | null
  /** Political lean preference: progressive | conservative | null = no preference declared. */
  political_preference?: 'progressive' | 'conservative' | null
  /** Household income for personalized housing affordability scoring. null = use local median. */
  household_income?: number | null
}

interface SearchOptionsProps {
  options: SearchOptions
  onChange: (options: SearchOptions) => void
  disabled?: boolean
  expanded?: boolean
  onExpandedChange?: (expanded: boolean) => void
  /** When true, do not load from or write to session storage (e.g. on saved place detail so row priorities are used). */
  skipSessionRestore?: boolean
}

const DEFAULT_PRIORITIES: PillarPriorities = {
  active_outdoors: 'Medium',
  natural_beauty: 'Medium',
  neighborhood_amenities: 'Medium',
  air_travel_access: 'Medium',
  public_transit_access: 'Medium',
  healthcare_access: 'Medium',
  economic_opportunity: 'Medium',
  quality_education: 'Medium',
  housing_value: 'Medium',
  climate_risk: 'Medium',
  social_fabric: 'Medium',
  diversity: 'None', // a preference, not a weight (owner decision 2026-10-28)
  community_safety: 'Medium',
  political_lean: 'None',
  commute_time: 'None',
  social_connection: 'None',
}

export const JOB_CATEGORY_OPTIONS: Array<{ key: string; label: string; description: string }> = [
  { key: 'tech_professional', label: 'Tech / Product', description: 'Software, data, engineering, product, UX/UI' },
  { key: 'business_finance_law', label: 'Business / Finance / Law', description: 'Finance, consulting, corporate, legal, accounting' },
  { key: 'healthcare_education', label: 'Healthcare / Education', description: 'Doctors, nurses, teachers, professors, admin' },
  { key: 'skilled_trades_logistics', label: 'Skilled trades / Logistics', description: 'Construction, manufacturing, transport, mechanics, electricians' },
  { key: 'service_retail_hospitality', label: 'Service / Retail / Hospitality', description: 'Restaurants, retail, tourism, personal services' },
  { key: 'public_sector_nonprofit', label: 'Public sector', description: 'Government and public administration (nonprofit proxy is limited)' },
  { key: 'remote_flexible', label: 'Remote / Flexible', description: 'Work-from-home prevalence + earnings proxy' },
]

/** Session key for premium school scoring code (shared with saved-place detail and API client). */
export const PREMIUM_CODE_KEY = 'homefit_premium_code'

export { DEFAULT_PRIORITIES }
export type { PillarPriorities, SearchOptions }
