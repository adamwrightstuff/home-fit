/**
 * Server-only loader for catalog neighborhood rows, used by the
 * per-neighborhood pages (app/neighborhoods/[slug]) and the sitemap.
 *
 * Reads the same pre-scored JSONL catalogs as app/api/catalog-map.
 * Rows are cached in memory for the lifetime of the process, so
 * generateStaticParams over 416 places reads each file once.
 */

import type { WorkCommute } from '@/lib/workZones'
import fs from 'fs'
import path from 'path'
import { CATALOG_METROS, type CatalogMetro } from './catalogMetros'
import { placeSlug } from './neighborhoodSlug'
import type { ScoreResponse } from '@/types/api'

export interface NeighborhoodCatalogInfo {
  name: string
  type?: string | null
  county_borough?: string | null
  state_abbr?: string | null
  state_full?: string | null
  lat?: number | string | null
  lon?: number | string | null
  search_query?: string | null
}

export interface NeighborhoodEntry {
  metro: CatalogMetro
  slug: string
  catalog: NeighborhoodCatalogInfo
  /** Full pre-scored payload (ScoreResponse shape). */
  score: ScoreResponse
  /** Precomputed minutes to each work hub, when this metro has them. */
  work_commute: WorkCommute | null
}

const METRO_FILES: Record<CatalogMetro, string> = {
  // BEGIN GENERATED server (scripts/metro_agent/registry.py; do not edit by hand)
  nyc: 'nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  la: 'la_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  sf: 'sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  seattle: 'seattle_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  austin: 'austin_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  chicago: 'chicago_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  philadelphia: 'philadelphia_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  dallas: 'dallas_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  houston: 'houston_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  phoenix: 'phoenix_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  san_antonio: 'san_antonio_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  sacramento: 'sacramento_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  las_vegas: 'las_vegas_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  orlando: 'orlando_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  tampa: 'tampa_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  // END GENERATED server
}

function dataRoots(): string[] {
  // Mirrors app/api/catalog-map/route.ts: repo-root data/ in dev,
  // frontend/data/ on Vercel (populated by the buildCommand copy).
  return [path.join(process.cwd(), '..', 'data'), path.join(process.cwd(), 'data')]
}

function findFile(name: string): string | null {
  for (const base of dataRoots()) {
    const p = path.join(base, name)
    try {
      if (fs.existsSync(p)) return p
    } catch {
      /* ignore */
    }
  }
  return null
}

let cache: NeighborhoodEntry[] | null = null

export function loadAllNeighborhoods(): NeighborhoodEntry[] {
  if (cache) return cache
  const entries: NeighborhoodEntry[] = []
  for (const metro of CATALOG_METROS) {
    const file = findFile(METRO_FILES[metro])
    if (!file) continue // metro not yet batch-scored; skip
    const raw = fs.readFileSync(file, 'utf8')
    for (const line of raw.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      try {
        const row = JSON.parse(trimmed) as {
          catalog?: NeighborhoodCatalogInfo
          score?: ScoreResponse
          work_commute?: WorkCommute | null
        }
        if (!row.catalog?.name || !row.score) continue
        entries.push({
          metro,
          slug: placeSlug(row.catalog),
          catalog: row.catalog,
          score: row.score,
          work_commute: row.work_commute ?? null,
        })
      } catch {
        /* skip malformed lines */
      }
    }
  }
  cache = entries
  return entries
}

export function findNeighborhoodBySlug(slug: string): NeighborhoodEntry | null {
  return loadAllNeighborhoods().find((e) => e.slug === slug) ?? null
}

export function getAllNeighborhoodSlugs(): string[] {
  return loadAllNeighborhoods().map((e) => e.slug)
}
