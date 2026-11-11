// Local Scene ladder (docs/LOCAL_SCENE_LADDER_DPV2.md). The keys match score.local_scene_level in the catalog.
// The display words are working names: change them here and in SCENE_COPY (lib/catalogInfoCopy.ts) and nowhere else.
export type SceneLevel = 'quiet' | 'low_key' | 'lively' | 'buzzing'

export const SCENE_LEVELS: SceneLevel[] = ['quiet', 'low_key', 'lively', 'buzzing']

export const SCENE_LABEL: Record<SceneLevel, string> = {
  quiet: 'Quiet',
  low_key: 'Low-key',
  lively: 'Lively',
  buzzing: 'Buzzing',
}

export function isSceneLevel(v: unknown): v is SceneLevel {
  return typeof v === 'string' && (SCENE_LEVELS as string[]).includes(v)
}

/** Explorer filter: 'all', 'Lively' (lively and buzzing) or 'Buzzing' (buzzing only). */
export type SceneFilter = 'all' | 'Lively' | 'Buzzing'

/** Reads a saved filter value, including values saved before the ladder existed (Some, High). */
export function normalizeSceneFilter(v: unknown): SceneFilter {
  if (v === 'Buzzing' || v === 'High') return 'Buzzing'
  if (v === 'Lively' || v === 'Some') return 'Lively'
  return 'all'
}

/** True when a place with this level is left out by the filter. A place with no level (no data) is always left out. */
export function sceneFilterExcludes(level: unknown, filter: SceneFilter): boolean {
  if (filter === 'all') return false
  if (filter === 'Buzzing') return level !== 'buzzing'
  return level !== 'lively' && level !== 'buzzing'
}
