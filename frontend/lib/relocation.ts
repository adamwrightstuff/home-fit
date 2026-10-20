import type { CatalogMapPlace, CatalogMapPlaceWithMetro } from '@/lib/catalogMapTypes'
import { catalogRowKey, inferCatalogMetro } from '@/lib/catalogMapTypes'

/** One priced view (renting or owning) from /api/relocation. */
export interface RelocationView {
  equivalent_income_in_dest: number
  change_pct: number
  housing_scale_source: string
  city_tax: { origin: string | null; dest: string | null }
}

export interface RelocationResult {
  estimate_note: string
  same_metro: boolean
  rent: RelocationView | null
  own: RelocationView | null
}

/** Where a catalog place sits for pricing: metro key, state, and city (for city income tax). */
export interface PlaceCtx {
  name: string
  metro: string
  state: string
  city: string
}

export function placeCtx(place: CatalogMapPlace): PlaceCtx {
  const li = (place.score as unknown as { location_info?: { city?: string } }).location_info
  return {
    name: place.catalog.name,
    metro: inferCatalogMetro(place as CatalogMapPlace & { metro?: never }),
    state: place.catalog.state_abbr ?? '',
    city: li?.city ?? '',
  }
}

let placesPromise: Promise<CatalogMapPlaceWithMetro[]> | null = null
/** All catalog places, fetched once per page load (same endpoint the profile home picker uses). */
export function loadCatalogPlaces(): Promise<CatalogMapPlaceWithMetro[]> {
  if (!placesPromise) {
    placesPromise = fetch('/api/catalog-map?metro=all')
      .then((r) => (r.ok ? r.json() : { places: [] }))
      .then((j) => (Array.isArray(j?.places) ? (j.places as CatalogMapPlaceWithMetro[]) : []))
      .catch(() => [])
  }
  return placesPromise
}

export async function findPlaceByKey(key: string): Promise<CatalogMapPlaceWithMetro | null> {
  return (await loadCatalogPlaces()).find((p) => catalogRowKey(p.catalog) === key) ?? null
}

/** The profile stores only the home's name; the first catalog place with that name is used. */
export async function findPlaceByName(name: string): Promise<CatalogMapPlaceWithMetro | null> {
  return (await loadCatalogPlaces()).find((p) => p.catalog.name === name) ?? null
}

const cache = new Map<string, Promise<RelocationResult | null>>()

export function fetchRelocation(
  origin: PlaceCtx,
  dest: PlaceCtx,
  income: number,
  monthlyCost: number | null,
): Promise<RelocationResult | null> {
  const q = new URLSearchParams({
    origin_metro: origin.metro,
    dest_metro: dest.metro,
    income: String(Math.round(income)),
  })
  if (monthlyCost && monthlyCost > 0) q.set('monthly_cost', String(Math.round(monthlyCost)))
  if (origin.state) q.set('origin_state', origin.state)
  if (dest.state) q.set('dest_state', dest.state)
  if (origin.city) q.set('origin_city', origin.city)
  if (dest.city) q.set('dest_city', dest.city)
  const key = q.toString()
  let p = cache.get(key)
  if (!p) {
    p = fetch(`/api/relocation?${key}`)
      .then((r) => (r.ok ? (r.json() as Promise<RelocationResult>) : null))
      .catch(() => null)
    cache.set(key, p)
  }
  return p
}
