// Pure functions, no imports, so node tests can load this file directly (tests/social_proximity.test.mjs).
// Spec sheet: docs/SOCIAL_PROXIMITY.md

/**
 * Two personal priorities (opt-in, client-side only, not pillars, not in the general happiness index).
 * Spec sheet: docs/SOCIAL_PROXIMITY.md. The user enters people tagged close or acquaintance.
 * - social_connection: close family and friends, straight-line MILES through the close curve, combined
 *   by socialConnectionScore. Miles because the study is in miles.
 * - acquaintances_nearby: acquaintances, scored on whether they live inside the place's walk zone
 *   (acquaintancesNearbyScore).
 * The place's area-type label is not an input to either (DPv2 principle 14).
 *
 * Close curve, a documented fit (owner approved 2026-11-05) to one study:
 * - Schoeni, Cho and Choi 2022 (Soc Sci Med 292:114627, PSID, 810 parents 55+ with a disability,
 *   1,767 parent and adult-child pairs), Appendix Table A2, adjusted weekly hours of help from an
 *   adult child by distance band (95% interval): up to 2 mi 1.20 (0.70 to 1.70); 2 to 5 mi 1.56
 *   (0.65 to 2.46); 5 to 10 mi 0.73 (0.32 to 1.15); 10 to 30 mi 0.43 (0.18 to 0.68); 30 to 100 mi
 *   0.75 (0.10 to 1.41); over 100 mi 0.56 (0.22 to 0.90). The raw bands are not monotone, so a
 *   decreasing (isotonic) fit weighted by inverse variance (SE = interval width / 3.92) pools them:
 *   up to 5 mi 1.28; 5 to 10 mi 0.73; 10 mi and beyond 0.50. Relative to the near value that is
 *   100, 57 and 39.
 *   Curve: 100 through 3.5 miles (midpoint of the 2 to 5 mile band, the top of the fitted near
 *   level), linear to 57 at 7.5 miles (midpoint of 5 to 10), linear to 39 at 20 miles (midpoint of
 *   10 to 30), flat beyond. Straight lines between midpoints are a choice, not a finding.
 *   Plausible ranges (parametric bootstrap, normal approximation from the published intervals,
 *   independent bands, 20,000 draws): 5 to 10 mi value 57 (31 to 100); 10 mi and beyond 39 (22 to 65).
 *   Not in the curve: the premium at the closest distances (same block about 2.7 times the 2 to 5 mile
 *   band, coresident more), which the curve leaves flat at 100. Construct caveat: this is help to
 *   disabled older parents, not wellbeing, and the paper notes possible endogeneity (families may
 *   have moved closer as health declined). Supporting, not used for a constant: Sun and Schafer 2023
 *   (SHARE): losing a relative within 1 km or a non-relative within about 5 km raises loneliness.
 *
 * Acquaintances are a separate priority (key acquaintances_nearby), not a weaker close tie. Close ties
 * work through planned visits and help (Hawkley and Cacioppo's intimate and relational loneliness);
 * acquaintances work through chance run-ins (collective loneliness and belonging). Huxhold, Fiori,
 * Webster and Antonucci 2020 (J Gerontol B 75(7), N = 802, 23 years) found the number of weaker ties
 * predicted lower depressed affect and higher positive affect more strongly than the number of close
 * ties, so nothing caps an acquaintance below a close tie, and the user's two priority levels weigh
 * them against each other (no research ratio exists). See docs/SOCIAL_PROXIMITY.md.
 */
export type SocialConnectionTier = 'close' | 'acquaintance'

export interface SocialConnectionPoint {
  lat: number
  lon: number
  tier: SocialConnectionTier
  label?: string
}

function validMiles(miles: number | null | undefined): miles is number {
  return typeof miles === 'number' && Number.isFinite(miles) && miles >= 0
}

export function closeTieProximityScore(miles: number | null | undefined): number | null {
  if (!validMiles(miles)) return null
  if (miles <= 3.5) return 100
  if (miles <= 7.5) return 100 - (miles - 3.5) * (43 / 4)
  if (miles <= 20) return 57 - (miles - 7.5) * (18 / 12.5)
  return 39
}

/**
 * Acquaintance walk zone, in meters because the evidence is walking distance, not travel miles.
 * Full credit within 800 m (common walk-access benchmark), straight line to 0 at 1,260 m (observed
 * 85th percentile walk to commuter rail, Montreal). Both are walk-to-destination evidence, borrowed for
 * walk-to-encounter; no study measures run-ins by distance. TODO, range unknown.
 */
export const ACQUAINTANCE_WALK_FULL_M = 800
export const ACQUAINTANCE_WALK_ZERO_M = 1260
const METERS_PER_MILE = 1609.344

export function acquaintanceProximityScore(miles: number | null | undefined): number | null {
  if (!validMiles(miles)) return null
  const m = miles * METERS_PER_MILE
  if (m <= ACQUAINTANCE_WALK_FULL_M) return 100
  if (m >= ACQUAINTANCE_WALK_ZERO_M) return 0
  return 100 * (ACQUAINTANCE_WALK_ZERO_M - m) / (ACQUAINTANCE_WALK_ZERO_M - ACQUAINTANCE_WALK_FULL_M)
}

/**
 * Close ties: nearest close person, plus a small flat bonus for each additional close person who is
 * also meaningfully close (up to a cap). Chosen over an earlier noisy-OR combine, which let a single
 * point saturate every place in that person's metro to ~100. Acquaintance points are ignored here;
 * they score under acquaintancesNearbyScore.
 *
 * The bonus amount (5), the cap (2 extras) and the threshold (70, a close person within about 6 miles)
 * are unsourced placeholders, all TODO with range unknown.
 */
const CLOSE_BONUS_THRESHOLD = 70
const SOCIAL_CONNECTION_BONUS_PER_EXTRA_POINT = 5
const SOCIAL_CONNECTION_MAX_BONUS_POINTS = 2

type TierMiles = { tier: SocialConnectionTier; miles: number | null | undefined; sameNeighborhood?: boolean }

export function socialConnectionScore(points: TierMiles[]): number | null {
  const scored: number[] = []
  for (const p of points) {
    if (p.tier !== 'close') continue
    const proximity = closeTieProximityScore(p.miles)
    if (proximity !== null) scored.push(proximity)
  }
  if (scored.length === 0) return null
  scored.sort((a, b) => b - a)
  const [best, ...rest] = scored
  const bonusEligibleCount = rest.filter((v) => v >= CLOSE_BONUS_THRESHOLD).length
  const bonus = Math.min(bonusEligibleCount, SOCIAL_CONNECTION_MAX_BONUS_POINTS) * SOCIAL_CONNECTION_BONUS_PER_EXTRA_POINT
  return Math.min(100, Math.round((best + bonus) * 10) / 10)
}

/**
 * Acquaintances: full credit at the neighborhood they live in (sameNeighborhood, see livesInPlace),
 * otherwise the best walk-zone score among acquaintances inside the zone. Anyone outside the walk
 * zone drops out rather than scoring 0, so an acquaintance can lift the places they live near but never
 * penalize the rest; with nobody inside, the result is null and the priority drops out of the total.
 * More acquaintances in the zone add nothing yet: the research supports the count of weak ties
 * mattering, but gives no mapping from count to score. TODO, range unknown.
 */
export function acquaintancesNearbyScore(points: TierMiles[]): number | null {
  let best: number | null = null
  for (const p of points) {
    if (p.tier !== 'acquaintance') continue
    const proximity = p.sameNeighborhood ? 100 : acquaintanceProximityScore(p.miles)
    if (proximity === null || proximity <= 0) continue
    if (best === null || proximity > best) best = proximity
  }
  return best === null ? null : Math.round(best * 10) / 10
}

const EARTH_RADIUS_M = 6371008.8

function metersBetween(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(bLat - aLat)
  const dLon = toRad(bLon - aLon)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h))
}

/**
 * Does the person live in this place? The data has no neighborhood boundaries, so a person lives in the
 * place whose center point is nearest to them (among the catalog centers and this place's own pin), and
 * no farther from it than the gap from that center to the next nearest center. The gap limit keeps
 * someone far outside every catalog place from being assigned to one. Both are geometric choices, not
 * findings; a large suburban place gives full credit across a distance no one walks. TODO, range unknown.
 * Centers within 1 m of the place are treated as the place itself (a catalog place's own entry).
 *
 * makeLivesInPlace caches each person's nearest center and each center's gap, so checking every
 * catalog place for one person costs one pass over the centers instead of one per place.
 */
export function makeLivesInPlace(centroids: ReadonlyArray<readonly [number, number]>) {
  const nearestByPerson = new Map<string, { index: number; meters: number }>()
  const gapByCenter = new Map<number, number>()
  const gapFrom = (lat: number, lon: number, skip?: number) => {
    let gap = Infinity
    for (let i = 0; i < centroids.length; i++) {
      if (i === skip) continue
      const d = metersBetween(lat, lon, centroids[i][0], centroids[i][1])
      if (d > 1) gap = Math.min(gap, d)
    }
    return gap
  }
  return function livesInPlace(person: { lat: number; lon: number }, place: { lat: number; lon: number }): boolean {
    const values = [person.lat, person.lon, place.lat, place.lon]
    if (!values.every((v) => typeof v === 'number' && Number.isFinite(v))) return false
    const key = `${person.lat},${person.lon}`
    let nearest = nearestByPerson.get(key)
    if (!nearest) {
      nearest = { index: -1, meters: Infinity }
      for (let i = 0; i < centroids.length; i++) {
        const d = metersBetween(person.lat, person.lon, centroids[i][0], centroids[i][1])
        if (d < nearest.meters) nearest = { index: i, meters: d }
      }
      nearestByPerson.set(key, nearest)
    }
    const toPlace = metersBetween(person.lat, person.lon, place.lat, place.lon)
    const home = nearest.index >= 0 ? centroids[nearest.index] : null
    if (home && metersBetween(place.lat, place.lon, home[0], home[1]) <= 1) {
      // the place is the person's nearest catalog center
      let gap = gapByCenter.get(nearest.index)
      if (gap === undefined) {
        gap = gapFrom(home[0], home[1], nearest.index)
        gapByCenter.set(nearest.index, gap)
      }
      return nearest.meters <= gap
    }
    // a pin that is not the person's nearest catalog center: it must beat every catalog center
    if (toPlace > nearest.meters) return false
    return toPlace <= gapFrom(place.lat, place.lon)
  }
}

/** One-off form of makeLivesInPlace, for tests and single checks. */
export function livesInPlace(
  person: { lat: number; lon: number },
  place: { lat: number; lon: number },
  centroids: ReadonlyArray<readonly [number, number]>
): boolean {
  return makeLivesInPlace(centroids)(person, place)
}
