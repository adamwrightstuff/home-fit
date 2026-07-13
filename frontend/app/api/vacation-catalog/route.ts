import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'
import type { VacationPlace } from '@/lib/vacationCatalogTypes'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

function dataRoots(): string[] {
  return [path.join(process.cwd(), '..', 'data'), path.join(process.cwd(), 'data')]
}

function findJsonl(): string | null {
  const name = 'vacation_destinations_scores.jsonl'
  for (const base of dataRoots()) {
    const p = path.join(base, name)
    try {
      if (fs.existsSync(p)) return p
    } catch {
      // ignore
    }
  }
  return null
}

export async function GET() {
  const filePath = findJsonl()
  if (!filePath) {
    return NextResponse.json({ error: 'vacation_destinations_scores.jsonl not found' }, { status: 404 })
  }

  const raw = fs.readFileSync(filePath, 'utf8')
  const seen = new Map<string, VacationPlace>()

  for (const line of raw.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    try {
      const row = JSON.parse(trimmed)
      if (!row.location || !row.trip_type || !row.pillars) continue
      const coords = row.score_data?.coordinates
      if (!coords?.lat || !coords?.lon) continue

      const key = `${row.location}|${row.trip_type}`
      const place: VacationPlace = {
        key,
        location: row.location,
        trip_type: row.trip_type,
        total_score: row.total_score ?? 0,
        lat: coords.lat,
        lon: coords.lon,
        pillars: row.pillars,
        allocation_type: row.allocation_type ?? null,
      }

      const prev = seen.get(key)
      if (!prev || place.total_score > prev.total_score) {
        seen.set(key, place)
      }
    } catch {
      // skip malformed lines
    }
  }

  return NextResponse.json({ places: Array.from(seen.values()) })
}
