/**
 * Build a single-row export of HomeFit scores for a place (CSV or copy).
 * Only includes pillars that have a score; omits incomplete pillars.
 */

import { PILLAR_ORDER, type PillarKey } from '@/lib/pillars'

type Importance = 'None' | 'Low' | 'Medium' | 'High'

function weightToExport(importance: Importance): string {
  switch (importance) {
    case 'Low':
      return 'low'
    case 'Medium':
      return 'med'
    case 'High':
      return 'high'
    default:
      return 'med'
  }
}

function escapeCsvCell(value: string | number): string {
  const s = String(value)
  if (/[,"\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`
  }
  return s
}

export interface ExportInput {
  /** Place display name (e.g. "Town of Mamaroneck, New York") */
  locationName: string
  lat: number
  lon: number
  homefitScore: number | null
  longevityScore: number | null
  happinessScore?: number | null
  /** Pillar key -> score (only pillars with valid scores; failed runs excluded) */
  pillarScores: Record<string, { score: number; failed?: boolean }>
  /** Pillar key -> user-selected importance */
  selectedPriorities: Record<string, Importance>
}

export interface ExportRow {
  headers: string[]
  values: (string | number)[]
  csvHeaderLine: string
  csvDataLine: string
  /** Full two-line block for copy (header + data) */
  copyBlock: string
}

/**
 * Build one row of export data: fixed columns (location, lat, lng, homefit_score, longevity_score, happiness_score)
 * then for each active pillar: pillar_name, pillar_name_weight.
 * Pillars with no score are omitted.
 */
export function buildExportRow(input: ExportInput): ExportRow {
  const {
    locationName,
    lat,
    lon,
    homefitScore,
    longevityScore,
    happinessScore,
    pillarScores,
    selectedPriorities,
  } = input

  const headers: string[] = ['location', 'lat', 'lng', 'homefit_score', 'longevity_score', 'happiness_score']
  const values: (string | number)[] = [
    locationName,
    lat,
    lon,
    homefitScore ?? '',
    longevityScore ?? '',
    happinessScore ?? '',
  ]

  for (const key of PILLAR_ORDER) {
    const scoreEntry = pillarScores[key]
    if (!scoreEntry || typeof scoreEntry.score !== 'number' || scoreEntry.failed) continue
    const weight = selectedPriorities[key] ?? 'Medium'
    headers.push(key, `${key}_weight`)
    values.push(Math.round(scoreEntry.score), weightToExport(weight))
  }

  const csvHeaderLine = headers.join(',')
  const csvDataLine = values.map((v) => escapeCsvCell(v)).join(',')

  const copyBlock = [csvHeaderLine, csvDataLine].join('\n')

  return {
    headers,
    values,
    csvHeaderLine,
    csvDataLine,
    copyBlock,
  }
}

/** Generate a safe filename slug from location name for CSV download. */
export function slugifyLocationForFilename(name: string): string {
  return name
    .replace(/[^a-zA-Z0-9\s,-]/g, '')
    .replace(/\s+/g, '_')
    .replace(/,/g, '')
    .slice(0, 60)
}
