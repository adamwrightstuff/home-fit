// Pure functions, no imports, so node tests can load this file directly (tests/social_proximity.test.mjs).
// Spec sheet: docs/SOCIAL_PROXIMITY.md

/**
 * Social-proximity score (personal priority, key social_connection; opt-in, client-side only, not
 * a pillar and not in the general happiness index). Spec sheet: docs/SOCIAL_PROXIMITY.md.
 * The user enters people (family and friends) tagged close or acquaintance; each person's
 * straight-line MILES to the place go through the tier's curve, then the people combine via
 * socialConnectionScore. Distance is miles on purpose: the studies are in miles and km, and the
 * place's area-type label is not an input (DPv2 principle 14).
 *
 * Close curve (shape from one verified study, constants mostly TODO):
 * - Schoeni, Cho and Choi 2022 (Soc Sci Med 292:114627, PSID, 810 parents 55+ with a disability):
 *   adjusted weekly hours of help from an adult child are 1.16 at 2-5 miles, 0.79 at 5-10 miles
 *   and 0.58 beyond 100 miles, and little help depends on distance past about 2-5 miles.
 *   So: 100 through 5 miles (the reference band), 68 at 7.5 miles (0.79 / 1.16), linear to a
 *   floor of 50 at 100 miles (0.58 / 1.16), flat beyond. The 10-30 and 30-100 mile bands were not
 *   retrieved, so the line between 7.5 and 100 miles is a TODO, and so is the 5 to 7.5 mile
 *   segment. Plausible range for the floor, from the paper's intervals: about 20 to 80.
 *   Construct caveat: this is help to disabled older parents, not wellbeing, and the paper notes
 *   possible endogeneity (families may have moved closer as health declined).
 * - Supporting, not used for a constant: Sun and Schafer 2023 (SHARE): losing a relative within
 *   1 km or a non-relative within about 5 km raises loneliness; farther losses not significant.
 *
 * Acquaintance curve: no evidence found. Kept as the previous curve converted to miles at the old
 * suburban baseline (2.4 minutes per mile): 100 through 7.5 miles, 55 at 12.5, 10 at 25, 0 at 31.
 * Every knot is a TODO with range unknown. It makes no research claim.
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
  if (miles <= 5) return 100
  if (miles <= 7.5) return 100 - (miles - 5) * (32 / 2.5)
  if (miles <= 100) return 68 - (miles - 7.5) * (18 / 92.5)
  return 50
}

export function acquaintanceProximityScore(miles: number | null | undefined): number | null {
  if (!validMiles(miles)) return null
  if (miles <= 7.5) return 100
  if (miles <= 12.5) return 100 - (miles - 7.5) * (45 / 5)
  if (miles <= 25) return 55 - (miles - 12.5) * (45 / 12.5)
  if (miles <= 31) return 10 - (miles - 25) * (10 / 6)
  return 0
}

const TIE_PROXIMITY_CURVE: Record<SocialConnectionTier, (miles: number | null | undefined) => number | null> = {
  close: closeTieProximityScore,
  acquaintance: acquaintanceProximityScore,
}

/**
 * Nearest-tie-plus-bonus: score is whoever's closest, plus a small flat bonus for each
 * additional point that's also meaningfully close (up to a cap). Chosen over an earlier
 * noisy-OR combine, which let a single point above the close-tie plateau instantly saturate
 * every place in that tie's whole metro to ~100 regardless of the rest of the list, with no way
 * to tell places in that metro apart on this pillar anymore. This version still lets one very
 * close tie carry most of the score, but multiple close ties add a visible, bounded bump
 * instead of an invisible ceiling effect.
 *
 * The bonus amount (5), the cap (2 extras) and the "counts as close" thresholds (close 70,
 * acquaintance 60) are unsourced placeholders, all TODO with range unknown. The older derivations
 * of the thresholds from minute-based curves no longer apply. On the current curves a threshold of
 * 70 means a close person within about 7 miles, and 60 means an acquaintance within about 11 miles.
 */
const SOCIAL_CONNECTION_BONUS_THRESHOLD: Record<SocialConnectionTier, number> = {
  close: 70,
  acquaintance: 60,
}
const SOCIAL_CONNECTION_BONUS_PER_EXTRA_POINT = 5
const SOCIAL_CONNECTION_MAX_BONUS_POINTS = 2

export function socialConnectionScore(
  points: Array<{ tier: SocialConnectionTier; miles: number | null | undefined }>
): number | null {
  const scored: Array<{ tier: SocialConnectionTier; proximity: number }> = []
  for (const p of points) {
    const proximity = TIE_PROXIMITY_CURVE[p.tier](p.miles)
    if (proximity === null) continue
    scored.push({ tier: p.tier, proximity })
  }
  if (scored.length === 0) return null
  scored.sort((a, b) => b.proximity - a.proximity)
  const [best, ...rest] = scored
  const bonusEligibleCount = rest.filter((p) => p.proximity >= SOCIAL_CONNECTION_BONUS_THRESHOLD[p.tier]).length
  const bonus = Math.min(bonusEligibleCount, SOCIAL_CONNECTION_MAX_BONUS_POINTS) * SOCIAL_CONNECTION_BONUS_PER_EXTRA_POINT
  return Math.min(100, Math.round((best.proximity + bonus) * 10) / 10)
}

