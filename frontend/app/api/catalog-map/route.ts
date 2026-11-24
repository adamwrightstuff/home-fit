import { NextResponse } from 'next/server'
import path from 'path'
import type { CatalogMapApiResponse, CatalogMapPlace } from '@/lib/catalogMapTypes'
import { slimPlace } from '@/lib/catalogSlim'
import { catalogRowKey } from '@/lib/catalogMapTypes'
import { CATALOG_METROS, isCatalogMetro } from '@/lib/catalogMetros'
import {
  CACHE_HEADERS,
  buildAllPayload,
  findMergedJsonl,
  getClimateIndex,
  loadMetroFile,
  missingDetail,
  type CatalogMapMetro,
} from '@/lib/catalogMapServer'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const raw = (searchParams.get('metro') ?? 'nyc').toLowerCase()

  const climateIndex = getClimateIndex()

  // Full (unslimmed) detail for one place; the list payload below drops per-pillar detail.
  const key = searchParams.get('key')
  if (key) {
    if (!isCatalogMetro(raw)) return NextResponse.json({ error: 'key needs a single metro' }, { status: 400 })
    const place = loadMetroFile(raw as CatalogMapMetro, climateIndex).find((p) => catalogRowKey(p.catalog) === key)
    if (!place) return NextResponse.json({ error: 'Place not found' }, { status: 404 })
    return NextResponse.json({ place }, { headers: CACHE_HEADERS })
  }

  if (raw === 'all') {
    const { body, found } = buildAllPayload()
    return NextResponse.json(body, found ? { headers: CACHE_HEADERS } : undefined)
  }

  if (!isCatalogMetro(raw)) {
    return NextResponse.json(
      { error: `Invalid metro. Use ${CATALOG_METROS.map((m) => `metro=${m}`).join(', ')}, or metro=all.` },
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

  const places = loadMetroFile(metro, climateIndex).map(slimPlace)

  return NextResponse.json({ places, source: path.basename(filePath) } satisfies CatalogMapApiResponse, { headers: CACHE_HEADERS })
}
