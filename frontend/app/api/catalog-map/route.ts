import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import type { CatalogMapApiResponse, CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { ScoreResponse } from '@/types/api'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

function findMergedJsonl(): string | null {
  const candidates = [
    path.join(process.cwd(), '..', 'data', 'nyc_metro_place_catalog_scores_merged.jsonl'),
    path.join(process.cwd(), 'data', 'nyc_metro_place_catalog_scores_merged.jsonl'),
  ]
  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) return p
    } catch {
      // ignore
    }
  }
  return null
}

export async function GET() {
  const filePath = findMergedJsonl()
  if (!filePath) {
    return NextResponse.json({
      places: [] as CatalogMapPlace[],
      source: 'missing',
      detail:
        'Catalog file not found. Add data/nyc_metro_place_catalog_scores_merged.jsonl at the repo root (or copy into frontend/data).',
    } satisfies CatalogMapApiResponse & { detail?: string })
  }

  const raw = fs.readFileSync(filePath, 'utf8')
  const places: CatalogMapPlace[] = []
  for (const line of raw.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    try {
      const row = JSON.parse(trimmed) as {
        success?: boolean
        catalog?: CatalogMapPlace['catalog']
        score?: ScoreResponse
      }
      if (!row.success || !row.catalog || !row.score) continue
      places.push({
        catalog: row.catalog,
        score: row.score,
      })
    } catch {
      // skip bad lines
    }
  }

  const body: CatalogMapApiResponse = {
    places,
    source: path.basename(filePath),
  }
  return NextResponse.json(body)
}
