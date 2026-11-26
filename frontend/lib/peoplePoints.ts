import centroids from './catalogCentroids.json'
import { haversineMiles } from '@/lib/workZones'
import { makeLivesInPlace, type SocialConnectionTier } from '@/lib/socialProximity'

const livesInPlace = makeLivesInPlace(centroids as unknown as ReadonlyArray<readonly [number, number]>)

/**
 * The people the user entered, as scoring points for one place: straight-line miles plus whether an
 * acquaintance lives in this place (nearest catalog center, see livesInPlace). Every page builds its
 * points here so a place scores the same on the map, in Compare and on the neighborhood page.
 * Rebuild catalogCentroids.json with scripts/catalog/build_catalog_centroids.py.
 */
export function peoplePoints(
  people: ReadonlyArray<{ lat: number; lon: number; tier: SocialConnectionTier; label?: string }>,
  placeLat: number,
  placeLon: number
): Array<{ tier: SocialConnectionTier; miles: number; label?: string; sameNeighborhood: boolean }> {
  return people.map((person) => ({
    tier: person.tier,
    miles: haversineMiles(person.lat, person.lon, placeLat, placeLon),
    label: person.label,
    sameNeighborhood:
      person.tier === 'acquaintance' &&
      livesInPlace(person, { lat: placeLat, lon: placeLon }),
  }))
}
