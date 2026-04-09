import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import type { CatalogMapApiResponse, CatalogMapPlace } from '@/lib/catalogMapTypes'
import type { ScoreResponse } from '@/types/api'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

export type CatalogMapMetro = 'nyc' | 'la'

const METRO_FILES: Record<CatalogMapMetro, readonly string[]> = {
  nyc: [
    'nyc_metro_place_catalog_scores_merged.with_composites.jsonl',
    'nyc_metro_place_catalog_scores_merged.jsonl',
  ],
  la: [
    'la_metro_place_catalog_scores_merged.with_composites.jsonl',
    'la_metro_place_catalog_scores_merged.jsonl',
  ],
}

function dataRoots(): string[] {
  return [path.join(process.cwd(), '..', 'data'), path.join(process.cwd(), 'data')]
}

function findMergedJsonl(metro: CatalogMapMetro): string | null {
  for (const name of METRO_FILES[metro]) {
    for (const base of dataRoots()) {
      const p = path.join(base, name)
      try {
        if (fs.existsSync(p)) return p
      } catch {
        // ignore
      }
    }
  }
  return null
}

function missingDetail(metro: CatalogMapMetro): string {
  const names = METRO_FILES[metro].join(' or ')
  return `Catalog file not found for ${metro.toUpperCase()}. Add repo data/${names} (or copy into frontend/data).`
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const raw = (searchParams.get('metro') ?? 'nyc').toLowerCase()
  if (raw !== 'nyc' && raw !== 'la') {
    return NextResponse.json(
      { error: 'Invalid metro. Use metro=nyc or metro=la.' },
      { status: 400 }
    )
  }
  const metro = raw as CatalogMapMetro

  const filePath = findMergedJsonl(metro)
  if (!filePath) {
    return NextResponse.json({
      places: [] as CatalogMapPlace[],
      source: 'missing',
      detail: missingDetail(metro),
    } satisfies CatalogMapApiResponse & { detail?: string })
  }

  const rawFile = fs.readFileSync(filePath, 'utf8')
  const places: CatalogMapPlace[] = []
  for (const line of rawFile.split('\n')) {
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
