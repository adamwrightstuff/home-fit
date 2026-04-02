/** Catalog map anchor colors — derived from index ramps (ramp-400 accents). */
import { RAMP_HEX, type IndexRampKey } from '@/lib/indexColorSystem'

export const CATALOG_INDEX_COLORS = {
  homefit: RAMP_HEX.purple[400],
  longevity: RAMP_HEX.teal[400],
  happiness: RAMP_HEX.blue[400],
  status: RAMP_HEX.coral[400],
} as const

export type CatalogIndexColorKey = keyof typeof CATALOG_INDEX_COLORS

export function catalogRampKey(id: CatalogIndexColorKey): IndexRampKey {
  switch (id) {
    case 'homefit':
      return 'purple'
    case 'longevity':
      return 'teal'
    case 'happiness':
      return 'blue'
    case 'status':
      return 'coral'
    default:
      return 'purple'
  }
}
