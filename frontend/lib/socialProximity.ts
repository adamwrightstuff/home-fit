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
 * Acquaintance curve: no evidence found. Kept as the previous curve converted to miles at the old
 * suburban baseline (2.4 minutes per mile): 100 through 7.5 miles, 55 at 12.5, 10 at 25, 0 at 31.
 * Every knot is a TODO with range unknown. It makes no research claim. After the close curve was
 * refit (2026-11-05) the old acquaintance knots scored above the close curve between 7.5 and about 12
 * miles, which makes no sense (a casual tie worth more than a close one), so the acquaintance score
 * is capped at the close score for the same distance. The cap is a consistency rule, not a finding.
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

export function acquaintanceProximityScore(miles: number | null | undefined): number | null {
  if (!validMiles(miles)) return null
  const old =
    miles <= 7.5 ? 100
    : miles <= 12.5 ? 100 - (miles - 7.5) * (45 / 5)
    : miles <= 25 ? 55 - (miles - 12.5) * (45 / 12.5)
    : miles <= 31 ? 10 - (miles - 25) * (10 / 6)
    : 0
  return Math.min(old, closeTieProximityScore(miles) as number)
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
 * 70 means a close person within about 6 miles, and 60 means an acquaintance within about 12 miles.
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

