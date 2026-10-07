import type { ScoreResponse } from '@/types/api'
import {
  applyUserIncomeToScore,
  estimatedDriveMinutes,
  withCommuteTimePillar,
  withSocialConnectionPillar,
} from '@/lib/reweight'
import { findWorkZone, haversineMiles } from '@/lib/workZones'
import type { UserProfile } from '@/lib/userProfile'

/**
 * Hubs only have precomputed routing for catalog places. For an arbitrary searched address the
 * commute is a straight-line + area-type-speed estimate, which is only meaningful inside the
 * hub's own metro; farther out the adjustment is skipped and the area-average commute stands.
 * Round placeholder, not a fitted value.
 */
export const MAX_HUB_ESTIMATE_MILES = 75

/**
 * Estimated one-way minutes from a place to the user's work hub, or null when it can't be
 * estimated honestly: no hub, a transit-only hub (drive estimates are unrealistic there), a
 * transit or active commute mode (the estimate is drive-only), or a place outside the hub's metro.
 */
export function estimateHubCommuteMinutes(
  lat: number,
  lon: number,
  areaType: string | null | undefined,
  zoneId: string | null | undefined,
  mode: UserProfile['commute_mode'] | undefined
): number | null {
  const zone = findWorkZone(zoneId ?? null)
  if (!zone || zone.transitOnly) return null
  if (mode === 'transit' || mode === 'active') return null
  if (haversineMiles(lat, lon, zone.lat, zone.lon) > MAX_HUB_ESTIMATE_MILES) return null
  return estimatedDriveMinutes(lat, lon, zone.lat, zone.lon, areaType)
}

/**
 * Layers a user's profile onto a place's score, from data already in the score response (no new
 * API calls): income re-scores housing affordability, a work hub replaces the area-average
 * commute in the happiness index, and people add the social_connection pillar. Each step is a
 * no-op when its profile field is missing, and the happiness index is recomputed along the way.
 * Call before reweightScoreResponseFromPriorities.
 */
export function applyProfileToScore(
  score: ScoreResponse,
  profile: Partial<UserProfile> | null | undefined,
  opts: { incomeOverride?: number | null } = {}
): ScoreResponse {
  if (!profile) return score
  let out = score

  const income = opts.incomeOverride ?? profile.household_income ?? null
  if (income) out = applyUserIncomeToScore(out, income)

  const lat = Number((out.coordinates as any)?.lat)
  const lon = Number((out.coordinates as any)?.lon)
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return out
  const areaType = (out as any).data_quality_summary?.area_classification?.area_type ?? null

  const commuteMinutes = estimateHubCommuteMinutes(lat, lon, areaType, profile.work_zone_id, profile.commute_mode)
  if (commuteMinutes !== null) out = withCommuteTimePillar(out, commuteMinutes)

  if (profile.people?.length) {
    const points = profile.people.map((person) => ({
      tier: person.tier,
      minutes: estimatedDriveMinutes(person.lat, person.lon, lat, lon, areaType),
      label: person.label,
    }))
    out = withSocialConnectionPillar(out, points)
  }

  return out
}
