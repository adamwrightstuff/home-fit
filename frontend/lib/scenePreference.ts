import { blendSceneArchetypes, personalizedSceneScore, type SceneArchetype } from '@/lib/vibeFeatures'

export type { SceneArchetype }

/**
 * Compute a personalized local_scene_score (0-100) by blending the selected
 * archetype weights against the stored sub-dimension breakdown.
 * Returns null when no archetypes are selected or breakdown is absent.
 */
export function applyScenePreferences(
  breakdown: Record<string, number> | null | undefined,
  archetypes: SceneArchetype[],
): number | null {
  if (!breakdown || archetypes.length === 0) return null
  const weights = blendSceneArchetypes(archetypes)
  if (!weights) return null
  return Math.round(personalizedSceneScore(breakdown, weights) * 100) / 100
}
