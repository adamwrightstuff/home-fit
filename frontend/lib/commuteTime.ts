/**
 * Pure commute-time helpers (no imports) so they can be tested without the app build.
 * See docs/COMMUTE_TIME.md. The curve is an unsourced placeholder (spec gap 1); the no-route
 * rule below is the one evidence-driven part: a place with no route in the mode the user chose
 * must score worst, not drop out and look better than a long-commute place.
 */

export type CommuteEntry = { transit?: number | null; drive?: number | null } | null | undefined
export type CommuteModeChoice = 'auto' | 'transit' | 'active' | null | undefined

export interface RouteSummary {
  /** Minutes the commute filter uses (transit only for transit-only hubs, else the faster mode); null when no mode has a time. */
  filterMinutes: number | null
  transit: number | null
  drive: number | null
}

/** Null only when the place has no stored entry for the hub (not routed at all). An entry with both modes null is a real "no route". */
export function summarizeRoute(entry: CommuteEntry, transitOnly: boolean): RouteSummary | null {
  if (!entry) return null
  const transit = typeof entry.transit === 'number' ? entry.transit : null
  const drive = typeof entry.drive === 'number' ? entry.drive : null
  const candidates = transitOnly ? [transit] : [transit, drive]
  const usable = candidates.filter((m): m is number => m !== null)
  return { filterMinutes: usable.length ? Math.min(...usable) : null, transit, drive }
}

/**
 * True when the place was routed to this hub and the user's chosen mode has no time:
 * transit chosen and no transit route, drive chosen at a drivable hub and no drive time, or no
 * mode chosen and neither usable mode has a time. Not "no route": active modes (never routed),
 * and drive to a transit-only hub (drive times there are unrealistic by design).
 */
export function isNoRoute(entry: CommuteEntry, transitOnly: boolean, mode: CommuteModeChoice): boolean {
  const s = summarizeRoute(entry, transitOnly)
  if (!s) return false
  if (mode === 'transit') return s.transit === null
  if (mode === 'auto') return !transitOnly && s.drive === null
  if (mode === 'active') return false
  return s.filterMinutes === null
}

/** Placeholder piecewise-linear curve, 100 at 15 min or less, 0 at 90 min or more. Unsourced. */
export function commuteTimeScore(minutes: number | null | undefined): number | null {
  if (minutes === null || minutes === undefined || !Number.isFinite(minutes) || minutes < 0) return null
  if (minutes <= 15) return 100
  if (minutes <= 30) return 100 - (minutes - 15) * (20 / 15)
  if (minutes <= 60) return 80 - (minutes - 30) * (30 / 30)
  if (minutes <= 90) return 50 - (minutes - 60) * (50 / 30)
  return 0
}

/**
 * Commute pillar score for a place: the curve score scaled by office days (linear blend toward 100),
 * or 0 scaled the same way when there is no route in the chosen mode. Null when there is nothing to
 * score (no minutes and not a no-route case).
 */
export function commutePillarScore(
  minutes: number | null | undefined,
  officeDays: number | null | undefined,
  noRoute = false
): number | null {
  const base = noRoute && (minutes === null || minutes === undefined) ? 0 : commuteTimeScore(minutes)
  if (base === null) return null
  const days = typeof officeDays === 'number' ? Math.min(5, Math.max(1, officeDays)) : 5
  return 100 - (100 - base) * (days / 5)
}
