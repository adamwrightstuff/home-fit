// Local Scene ladder (docs/LOCAL_SCENE_LADDER_DPV2.md). The keys match score.local_scene_level in the catalog.
// Display words (owner decision 2026-11-11): Sleepy, Flat, Lively, Buzzing. Change them here and in SCENE_COPY (lib/catalogInfoCopy.ts) only;
// the stored keys (quiet, low_key, ...) stay as they are so the catalog files do not change.
export type SceneLevel = 'quiet' | 'low_key' | 'lively' | 'buzzing'

export const SCENE_LEVELS: SceneLevel[] = ['quiet', 'low_key', 'lively', 'buzzing']

export const SCENE_LABEL: Record<SceneLevel, string> = {
  quiet: 'Sleepy',
  low_key: 'Flat',
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
