import type { PillarPriorities } from '@/components/SearchOptions'
import { buildResultsCacheKey, canonicalizePrioritiesJsonFromSearchParam, type ResultsRouteParams } from '@/lib/resultsShare'
import { writeCatalogResultsHydrate } from '@/lib/catalogResultsHydrate'
import type { ScoreResponse } from '@/types/api'

/** One row from POST /api/agent/recommend (matches FastAPI agent_recommend). */
export interface AgentRecommendation {
  neighborhood: string
  archetype: string
  /** Status-signature label from scoring data, not a statistical percentile. */
  percentile_band: string
  match_score: number
  top_drivers: string[]
  explanation: string
  results_url: string
  /** Full score payload for sessionStorage hydrate (same pattern as NYC catalog map). */
  score?: ScoreResponse
}

/**
 * Before navigating to /results from an agent card, stash the score so the results
 * page hydrates immediately (matches catalog map writeCatalogResultsHydrate).
 */
export function hydrateRecommendationResultsNavigation(rec: AgentRecommendation): void {
  if (!rec.score || typeof window === 'undefined') return
  try {
    const url = new URL(rec.results_url, window.location.origin)
    const location = url.searchParams.get('location') ?? rec.neighborhood
    const prioritiesJson = canonicalizePrioritiesJsonFromSearchParam(url.searchParams.get('priorities'))
    const routeParams: ResultsRouteParams = {
      location,
      prioritiesJson,
      job_categories: null,
      include_chains: false,
      enable_schools: false,
      natural_beauty_preference: null,
      built_character_preference: null,
      built_density_preference: null,
    }
    const cacheKey = buildResultsCacheKey(routeParams)
    writeCatalogResultsHydrate({ v: 1, cacheKey, score: rec.score })
  } catch {
    // non-fatal; /results will run a live score
  }
}

export interface AgentRecommendMeta {
  model: string
  neighborhoods_evaluated: number
  processing_ms: number
}

export interface AgentRecommendResponse {
  recommendations: AgentRecommendation[]
  meta: AgentRecommendMeta
}

/** Serializable quiz snapshot for the agent (matches PlaceValuesGame QuizAnswers shape). */
export function quizAnswersToAgentContext(answers: {
  life_stage: string | null
  weekend_energy: string | null
  car_relationship: string | null
  horizon: string | null
  natural_scenery: string[]
  job_categories: string[]
  community_vibe: string | null
}): Record<string, unknown> {
  return {
    life_stage: answers.life_stage,
    weekend_energy: answers.weekend_energy,
    car_relationship: answers.car_relationship,
    horizon: answers.horizon,
    natural_scenery: answers.natural_scenery,
    community_vibe: answers.community_vibe,
    ...(answers.job_categories.length > 0 ? { job_categories: answers.job_categories } : {}),
  }
}

export async function fetchAgentRecommendations(
  priorities: PillarPriorities,
  context: Record<string, unknown>
): Promise<AgentRecommendResponse> {
  const res = await fetch('/api/agent/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ priorities, context }),
    cache: 'no-store',
  })
  let data: unknown = {}
  try {
    data = await res.json()
  } catch {
    data = {}
  }
  const obj = data as { detail?: string }
  if (!res.ok) {
    const detail = typeof obj.detail === 'string' ? obj.detail : `Request failed (${res.status})`
    throw new Error(detail)
  }
  return data as AgentRecommendResponse
}
