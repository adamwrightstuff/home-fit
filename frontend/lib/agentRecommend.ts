import type { PillarPriorities } from '@/components/SearchOptions'

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
