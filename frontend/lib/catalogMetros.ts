/**
 * Single registry of catalog metros. Adding a metro = one entry here, plus its JSONL in
 * route.ts / next.config.js (see docs/METRO_EXPANSION_PLAYBOOK.md, Phase B).
 */
export const CATALOG_METROS = ['nyc', 'la', 'sf', 'seattle', 'austin', 'chicago', 'philadelphia', 'dallas'] as const
export type CatalogMetro = (typeof CATALOG_METROS)[number]

export interface CatalogMetroMeta {
  /** Short chip label. */
  label: string
  /** Name for pickers. */
  longLabel: string
  color: string
  /** [[lonMin, latMin], [lonMax, latMax]] */
  bounds: [[number, number], [number, number]]
}

export const CATALOG_METRO_META: Record<CatalogMetro, CatalogMetroMeta> = {
  nyc: { label: 'NYC', longLabel: 'New York metro', color: '#6B5CE7', bounds: [[-74.35, 40.45], [-73.65, 41.05]] },
  la: { label: 'LA', longLabel: 'Los Angeles metro', color: '#E76B5C', bounds: [[-118.75, 33.55], [-117.55, 34.45]] },
  sf: { label: 'SF', longLabel: 'Bay Area', color: '#2A9D8F', bounds: [[-122.7, 37.2], [-121.7, 38.2]] },
  seattle: { label: 'SEA', longLabel: 'Seattle metro', color: '#1A8FBF', bounds: [[-122.65, 47.45], [-122.1, 47.85]] },
  austin: { label: 'ATX', longLabel: 'Austin metro', color: '#D98E04', bounds: [[-98.1, 30.0], [-97.4, 30.7]] },
  chicago: { label: 'CHI', longLabel: 'Chicago metro', color: '#C2417A', bounds: [[-88.4, 41.5], [-87.4, 42.3]] },
  philadelphia: { label: 'PHL', longLabel: 'Philadelphia metro', color: '#5B8C3A', bounds: [[-75.6, 39.7], [-74.8, 40.3]] },
  dallas: { label: 'DFW', longLabel: 'Dallas-Fort Worth metro', color: '#B5651D', bounds: [[-97.9, 32.5], [-96.3, 33.4]] },
}

export function isCatalogMetro(v: unknown): v is CatalogMetro {
  return typeof v === 'string' && (CATALOG_METROS as readonly string[]).includes(v)
}

export function zeroMetroCounts(): Record<CatalogMetro, number> {
  return Object.fromEntries(CATALOG_METROS.map((m) => [m, 0])) as Record<CatalogMetro, number>
}
