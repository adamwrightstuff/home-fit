import zonesByMetro from './workZones.json'

export type WorkZoneMetro = 'nyc' | 'sf' | 'la' | 'seattle'

export interface WorkZone {
  id: string
  label: string
  lat: number
  lon: number
  metro: WorkZoneMetro
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

/** Fastest mode to a zone, or null when the place has no precomputed times for it. */
export function fastestCommute(
  commute: WorkCommute | null | undefined,
  zoneId: string,
): { minutes: number; mode: 'transit' | 'drive' } | null {
  const c = commute?.[zoneId]
  if (!c) return null
  const t = typeof c.transit === 'number' ? c.transit : null
  const d = typeof c.drive === 'number' ? c.drive : null
  if (t === null && d === null) return null
  if (d === null || (t !== null && t <= d)) return { minutes: t as number, mode: 'transit' }
  return { minutes: d, mode: 'drive' }
}
