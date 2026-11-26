/**
 * Surroundings: median household income and median home value around a place, next to its own.
 * Display only: no score, no weight, not counted in any total (docs/SURROUNDINGS.md).
 * Built offline by scripts/catalog/build_catalog_surroundings.py into data/catalog_surroundings.json.
 */

export type SurroundingsFigure = { here: number; around: number }
export type Surroundings = {
  income?: SurroundingsFigure
  home_value?: SurroundingsFigure
  /** Community safety score (0-100), only from places whose crime rate is their own (no city-wide, county or state rates). */
  safety?: SurroundingsFigure
  /** The closest catalog places, nearest first. */
  neighbors?: string[]
}

export type SurroundingsRow = { label: string; around: string; here: string }

function thousands(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(v >= 10_000_000 ? 0 : 1)}M`
  return `$${Math.round(v / 1000).toLocaleString('en-US')}k`
}

export function surroundingsRows(s: Surroundings | null | undefined): SurroundingsRow[] {
  if (!s) return []
  const rows: SurroundingsRow[] = []
  if (s.income) rows.push({ label: 'Household income', around: thousands(s.income.around), here: thousands(s.income.here) })
  if (s.home_value) rows.push({ label: 'Home value', around: thousands(s.home_value.around), here: thousands(s.home_value.here) })
  if (s.safety) rows.push({ label: 'Safety score', around: String(Math.round(s.safety.around)), here: String(Math.round(s.safety.here)) })
  return rows
}

export const SURROUNDINGS_EXPLAINER =
  'Medians from the Census (ACS 2022). "Nearby" averages the other places in this catalog within about 8 miles, ' +
  'weighted toward the closest, so towns we have not scored are not included. Neighbors at the Census cap ' +
  '($250,000 income, $2,000,000 home value) count at the cap. Safety (0 to 100, higher is safer) uses only places ' +
  'with their own crime rate; places on a city-wide, county or sheriff rate are left out. A description, not a score.'
