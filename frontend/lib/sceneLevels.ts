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

/** Explorer filter: the levels a person picked. Empty means no filter. */
export type SceneFilter = SceneLevel[]

/** Reads a saved filter value: a list of levels, or a value saved before multi-select (all, Some, Lively, High, Buzzing). */
export function normalizeSceneFilter(v: unknown): SceneFilter {
  if (Array.isArray(v)) return SCENE_LEVELS.filter(l => v.includes(l))
  if (v === 'Buzzing' || v === 'High') return ['buzzing']
  if (v === 'Lively' || v === 'Some') return ['lively', 'buzzing']
  return []
}

/** True when a place with this level is left out by the filter. With a filter on, a place with no level (no data) is left out. */
export function sceneFilterExcludes(level: unknown, filter: SceneFilter): boolean {
  if (filter.length === 0) return false
  return !(isSceneLevel(level) && filter.includes(level))
}

export function toggleSceneLevel(filter: SceneFilter, level: SceneLevel): SceneFilter {
  return filter.includes(level) ? filter.filter(l => l !== level) : SCENE_LEVELS.filter(l => l === level || filter.includes(l))
}
