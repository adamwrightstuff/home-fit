export type ResultsRouteParams = {
  location: string
  prioritiesJson: string
  job_categories?: string | null
  include_chains?: boolean
  enable_schools?: boolean
  natural_beauty_preference?: string | null
  built_character_preference?: string | null
  built_density_preference?: string | null
}

function stableHash(input: string): string {
  // Non-crypto stable hash for sessionStorage keys
  let h = 5381
  for (let i = 0; i < input.length; i++) h = ((h << 5) + h) ^ input.charCodeAt(i)
  return (h >>> 0).toString(16)
}

export function buildResultsCacheKey(p: ResultsRouteParams): string {
  const keyParts = [
    `location=${p.location}`,
    `priorities=${p.prioritiesJson}`,
    `job_categories=${p.job_categories ?? ''}`,
    `include_chains=${p.include_chains ? '1' : '0'}`,
    `enable_schools=${p.enable_schools ? '1' : '0'}`,
    `natural_beauty_preference=${p.natural_beauty_preference ?? ''}`,
    `built_character_preference=${p.built_character_preference ?? ''}`,
    `built_density_preference=${p.built_density_preference ?? ''}`,
  ].join('&')
  return `homefit_results_cache:${stableHash(keyParts)}`
}

export function buildResultsUrl(p: ResultsRouteParams): string {
  const usp = new URLSearchParams()
  usp.set('location', p.location)
  usp.set('priorities', p.prioritiesJson)
  if (p.job_categories) usp.set('job_categories', p.job_categories)
  if (p.include_chains) usp.set('include_chains', '1')
  if (p.enable_schools) usp.set('enable_schools', '1')
  if (p.natural_beauty_preference) usp.set('natural_beauty_preference', p.natural_beauty_preference)
  if (p.built_character_preference) usp.set('built_character_preference', p.built_character_preference)
  if (p.built_density_preference) usp.set('built_density_preference', p.built_density_preference)
  return `/results?${usp.toString()}`
}

