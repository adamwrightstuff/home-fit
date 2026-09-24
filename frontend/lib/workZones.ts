import zonesByMetro from './workZones.json'

export type WorkZoneMetro = 'nyc' | 'sf' | 'la' | 'seattle'

export interface WorkZone {
  id: string
  label: string
  lat: number
  lon: number
  metro: WorkZoneMetro
  /** Hubs people reach by transit (parking makes Google's drive time unrealistic); filter ignores drive. */
  transitOnly?: boolean
}

/** Precomputed fastest weekday-morning minutes per mode (see scripts/manual/add_work_zone_commutes.py). */
export type WorkCommute = Record<string, { transit?: number | null; drive?: number | null }>

export const WORK_ZONES: WorkZone[] = (Object.entries(zonesByMetro) as [WorkZoneMetro, Omit<WorkZone, 'metro'>[]][])
  .flatMap(([metro, zones]) => zones.map((z) => ({ ...z, metro })))

/** Addresses farther than this from every hub are rejected rather than snapped. */
export const MAX_SNAP_KM = 25

export function findWorkZone(id: string | null): WorkZone | null {
  return (id && WORK_ZONES.find((z) => z.id === id)) || null
}

function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(bLat - aLat)
  const dLon = toRad(bLon - aLon)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2
  return 6371 * 2 * Math.asin(Math.sqrt(h))
}

/** Zones that have precomputed times on at least one place (metros not yet run are hidden). */
export function availableWorkZones(places: { work_commute?: WorkCommute | null }[]): WorkZone[] {
  const ids = new Set<string>()
  for (const p of places) for (const id of Object.keys(p.work_commute ?? {})) ids.add(id)
  return WORK_ZONES.filter((z) => ids.has(z.id))
}

export function snapToWorkZone(lat: number, lon: number, zones: WorkZone[] = WORK_ZONES): { zone: WorkZone; km: number } | null {
  let best: { zone: WorkZone; km: number } | null = null
  for (const zone of zones) {
    const km = haversineKm(lat, lon, zone.lat, zone.lon)
    if (!best || km < best.km) best = { zone, km }
  }
  return best && best.km <= MAX_SNAP_KM ? best : null
}

/**
 * Commute to a zone: both modes for display, plus the minutes the commute filter uses
 * (transit only for transitOnly hubs, otherwise the faster mode). Null when nothing is precomputed.
 */
export function commuteToZone(
  commute: WorkCommute | null | undefined,
  zone: WorkZone,
): { filterMinutes: number | null; transit: number | null; drive: number | null } | null {
  const c = commute?.[zone.id]
  if (!c) return null
  const transit = typeof c.transit === 'number' ? c.transit : null
  const drive = typeof c.drive === 'number' ? c.drive : null
  if (transit === null && drive === null) return null
  const candidates = zone.transitOnly ? [transit] : [transit, drive]
  const usable = candidates.filter((m): m is number => m !== null)
  return { filterMinutes: usable.length ? Math.min(...usable) : null, transit, drive }
}

/** Card line, e.g. "Financial District: 57 min transit · 67 min drive". */
export function formatZoneCommute(zone: WorkZone, c: { transit: number | null; drive: number | null }): string {
  const parts = [
    c.transit !== null ? `${Math.round(c.transit)} min transit` : 'no transit route',
    c.drive !== null ? `${Math.round(c.drive)} min drive` : null,
  ].filter(Boolean)
  return `${zone.label}: ${parts.join(' · ')}`
}
