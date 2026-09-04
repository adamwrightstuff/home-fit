import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import type { CatalogMapApiResponse, CatalogMapPlace, CatalogMapPlaceWithMetro, ClimateIndicators } from '@/lib/catalogMapTypes'
import type { ScoreResponse } from '@/types/api'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

export type CatalogMapMetro = 'nyc' | 'la' | 'sf'

/** Single canonical file per metro (composites live inside each row's `score`). */
const METRO_FILES: Record<CatalogMapMetro, readonly string[]> = {
  nyc: ['nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl'],
  la: ['la_metro_place_catalog_scores_merged.composites_recomputed.jsonl'],
  sf: ['sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl'],
}

function dataRoots(): string[] {
  return [path.join(process.cwd(), '..', 'data'), path.join(process.cwd(), 'data')]
}

function findFile(name: string): string | null {
  for (const base of dataRoots()) {
    const p = path.join(base, name)
    try { if (fs.existsSync(p)) return p } catch { /* ignore */ }
  }
  return null
}

function findMergedJsonl(metro: CatalogMapMetro): string | null {
  for (const name of METRO_FILES[metro]) {
    const p = findFile(name)
    if (p) return p
  }
  return null
}

function missingDetail(metro: CatalogMapMetro): string {
  const names = METRO_FILES[metro].join(' or ')
  return `Catalog file not found for ${metro.toUpperCase()}. Add repo data/${names} (or copy into frontend/data).`
}

/** Load catalog_climate_profiles.jsonl → map of place name → ClimateIndicators */
function loadClimateIndex(): Map<string, ClimateIndicators> {
  const filePath = findFile('catalog_climate_profiles.jsonl')
  const index = new Map<string, ClimateIndicators>()
  if (!filePath) return index
  try {
    const raw = fs.readFileSync(filePath, 'utf8')
    for (const line of raw.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      try {
        const row = JSON.parse(trimmed) as {
          name: string
          climate?: { months?: Array<{ month: number; avg_temp_f: number; avg_precip_in: number; solar_kwh_m2_day: number }> }
        }
        const months = row.climate?.months
        if (!months?.length) continue
        const byMonth = Object.fromEntries(months.map((m) => [m.month, m]))
        const jan = byMonth[1]
        const jul = byMonth[7]
        if (!jan?.avg_temp_f || !jul?.avg_temp_f) continue
        const annual_precip_in = months.reduce((s, m) => s + (m.avg_precip_in ?? 0), 0)
        const solar_vals = months.map((m) => m.solar_kwh_m2_day).filter((v) => v != null)
        const avg_solar = solar_vals.length ? solar_vals.reduce((a, b) => a + b, 0) / solar_vals.length : 4.5
        index.set(row.name, {
          jan_f: jan.avg_temp_f,
          jul_f: jul.avg_temp_f,
          swing_f: jul.avg_temp_f - jan.avg_temp_f,
          annual_precip_in: Math.round(annual_precip_in * 10) / 10,
          avg_solar: Math.round(avg_solar * 100) / 100,
        })
      } catch { /* skip bad lines */ }
    }
  } catch { /* file unreadable */ }
  return index
}

function loadMetroFile(metro: CatalogMapMetro, climateIndex: Map<string, ClimateIndicators>): CatalogMapPlaceWithMetro[] {
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
      const place: CatalogMapPlaceWithMetro = { catalog: row.catalog, score: row.score, metro, cbd_transit_minutes: (row as any).cbd_transit_minutes ?? null }
      const climate = climateIndex.get(row.catalog.name)
      if (climate) place.climate = climate
      places.push(place)
    } catch {
      // skip bad lines
    }
  }
  return places
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const raw = (searchParams.get('metro') ?? 'nyc').toLowerCase()

  const climateIndex = loadClimateIndex()

  if (raw === 'all') {
    const nyc = loadMetroFile('nyc', climateIndex)
    const la = loadMetroFile('la', climateIndex)
    const sf = loadMetroFile('sf', climateIndex)
    const places: CatalogMapPlaceWithMetro[] = [...nyc, ...la, ...sf]
    const sources = [nyc.length ? 'nyc' : null, la.length ? 'la' : null, sf.length ? 'sf' : null].filter(Boolean).join('+') || 'missing'
    return NextResponse.json({
      places,
      source: sources === 'missing' ? 'missing' : `all:${sources}`,
    } satisfies CatalogMapApiResponse & { detail?: string })
  }

  if (raw !== 'nyc' && raw !== 'la' && raw !== 'sf') {
    return NextResponse.json(
      { error: 'Invalid metro. Use metro=nyc, metro=la, metro=sf, or metro=all.' },
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

  const places = loadMetroFile(metro, climateIndex).map(({ metro: _m, ...rest }) => rest as CatalogMapPlace)

  return NextResponse.json({ places, source: path.basename(filePath) } satisfies CatalogMapApiResponse)
}
