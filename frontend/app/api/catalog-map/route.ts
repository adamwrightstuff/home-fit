import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import type { CatalogMapApiResponse, CatalogMapPlace, CatalogMapPlaceWithMetro } from '@/lib/catalogMapTypes'
import type { ScoreResponse } from '@/types/api'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

export type CatalogMapMetro = 'nyc' | 'la'

/** Single canonical file per metro (composites live inside each row’s `score`). */
const METRO_FILES: Record<CatalogMapMetro, readonly string[]> = {
  nyc: ['nyc_metro_place_catalog_scores_merged.jsonl'],
  la: ['la_metro_place_catalog_scores_merged.jsonl'],
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

function loadMetroFile(metro: CatalogMapMetro): CatalogMapPlaceWithMetro[] {
  const filePath = findMergedJsonl(metro)
  if (!filePath) return []
  const rawFile = fs.readFileSync(filePath, 'utf8')
  const places: CatalogMapPlaceWithMetro[] = []
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
        metro,
      })
    } catch {
      // skip bad lines
    }
  }
  return places
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const raw = (searchParams.get('metro') ?? 'nyc').toLowerCase()

  if (raw === 'all') {
    const nyc = loadMetroFile('nyc')
    const la = loadMetroFile('la')
    const places: CatalogMapPlaceWithMetro[] = [...nyc, ...la]
    const sources = [nyc.length ? 'nyc' : null, la.length ? 'la' : null].filter(Boolean).join('+') || 'missing'
    return NextResponse.json({
      places,
      source: sources === 'missing' ? 'missing' : `all:${sources}`,
    } satisfies CatalogMapApiResponse & { detail?: string })
  }

  if (raw !== 'nyc' && raw !== 'la') {
    return NextResponse.json(
      { error: 'Invalid metro. Use metro=nyc, metro=la, or metro=all.' },
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

  const places = loadMetroFile(metro).map(({ metro: _m, ...rest }) => rest as CatalogMapPlace)

  const body: CatalogMapApiResponse = {
    places,
    source: path.basename(filePath),
  }
  return NextResponse.json(body)
}
