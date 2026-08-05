import type { TravelerProfile } from '@/components/vacation/TravelerProfileSelector'
import type { VacationPlace } from './vacationCatalogTypes'

export interface ProfileMeta {
  value: TravelerProfile
  emoji: string
  label: string
  tagline: string
}

export const PROFILE_META: ProfileMeta[] = [
  { value: 'adventurer',    emoji: '🧗', label: 'Adventurer',  tagline: 'Trails & peaks' },
  { value: 'relaxer',       emoji: '🌿', label: 'Relaxer',     tagline: 'Scenery & calm' },
  { value: 'culture',       emoji: '🎭', label: 'Culture',     tagline: 'Food & art' },
  { value: 'family',        emoji: '👨‍👩‍👧', label: 'Family',     tagline: 'Safe & fun' },
  { value: 'remote_worker', emoji: '💻', label: 'Remote Work', tagline: 'Extended stay' },
]

// AT fixed at 15% for all profiles. Mirrors pillars/vacation_weights.py TRAVELER_PROFILE_WEIGHTS.
const PROFILE_WEIGHTS: Record<TravelerProfile, Record<string, Record<string, number>>> = {
  adventurer: {
    beach:    { active_outdoors: 36, natural_beauty: 26, neighborhood_amenities: 8,  air_travel_access: 15, healthcare_access: 7,  climate_risk: 8  },
    mountain: { active_outdoors: 44, natural_beauty: 28, neighborhood_amenities: 4,  air_travel_access: 15, healthcare_access: 5,  climate_risk: 4  },
    city:     { active_outdoors: 30, natural_beauty: 12, neighborhood_amenities: 20, air_travel_access: 15, healthcare_access: 8, climate_risk: 15 },
  },
  relaxer: {
    beach:    { active_outdoors: 10, natural_beauty: 44, neighborhood_amenities: 18, air_travel_access: 15, healthcare_access: 3,  climate_risk: 10 },
    mountain: { active_outdoors: 15, natural_beauty: 50, neighborhood_amenities: 8,  air_travel_access: 15, healthcare_access: 3,  climate_risk: 9  },
    city:     { active_outdoors: 8,  natural_beauty: 30, neighborhood_amenities: 32, air_travel_access: 15, healthcare_access: 5, climate_risk: 10 },
  },
  culture: {
    beach:    { active_outdoors: 10, natural_beauty: 18, neighborhood_amenities: 48, air_travel_access: 15, healthcare_access: 3,  climate_risk: 6  },
    mountain: { active_outdoors: 12, natural_beauty: 22, neighborhood_amenities: 38, air_travel_access: 15, healthcare_access: 3,  climate_risk: 10 },
    city:     { active_outdoors: 5,  natural_beauty: 7,  neighborhood_amenities: 70, air_travel_access: 15, healthcare_access: 3, climate_risk: 0 },
  },
  family: {
    beach:    { active_outdoors: 18, natural_beauty: 24, neighborhood_amenities: 28, air_travel_access: 15, healthcare_access: 10, climate_risk: 5  },
    mountain: { active_outdoors: 22, natural_beauty: 26, neighborhood_amenities: 18, air_travel_access: 15, healthcare_access: 10, climate_risk: 9  },
    city:     { active_outdoors: 8,  natural_beauty: 10, neighborhood_amenities: 35, air_travel_access: 15, healthcare_access: 20, climate_risk: 12 },
  },
  remote_worker: {
    beach:    { active_outdoors: 12, natural_beauty: 22, neighborhood_amenities: 35, air_travel_access: 15, healthcare_access: 4,  climate_risk: 12 },
    mountain: { active_outdoors: 16, natural_beauty: 24, neighborhood_amenities: 32, air_travel_access: 15, healthcare_access: 4,  climate_risk: 9  },
    city:     { active_outdoors: 7,  natural_beauty: 10, neighborhood_amenities: 50, air_travel_access: 15, healthcare_access: 3, climate_risk: 15 },
  },
}

/**
 * Recompute a place's total score using a traveler profile's weights.
 * Falls back to the stored total_score when the profile has no weight map for this trip_type,
 * or when pillar scores are missing.
 */
export function recomputeScoreWithProfile(
  place: VacationPlace,
  profile: TravelerProfile | null,
): number {
  if (!profile) return place.total_score

  const tripWeights = PROFILE_WEIGHTS[profile]?.[place.trip_type]
  if (!tripWeights) return place.total_score

  let weighted = 0
  let totalWeight = 0
  for (const [pillar, weight] of Object.entries(tripWeights)) {
    const score = place.pillars[pillar]?.score
    if (score == null || weight === 0) continue
    weighted += score * weight
    totalWeight += weight
  }

  if (totalWeight === 0) return place.total_score
  // Normalize in case weights don't sum exactly to 100 due to null pillars
  return Math.round((weighted / totalWeight) * 10) / 10
}

// Mirrors VACATION_WEIGHT_PRESETS in pillars/vacation_weights.py (BE excluded from city).
const BASE_VACATION_WEIGHTS: Record<string, Record<string, number>> = {
  beach:    { active_outdoors: 24, natural_beauty: 30, neighborhood_amenities: 21, air_travel_access: 15, healthcare_access: 2,  climate_risk: 8  },
  mountain: { active_outdoors: 32, natural_beauty: 35, neighborhood_amenities: 10, air_travel_access: 12, healthcare_access: 3,  climate_risk: 8  },
  city:     { active_outdoors: 10, natural_beauty: 16, neighborhood_amenities: 45, air_travel_access: 15, healthcare_access: 5,  climate_risk: 9  },
}

/**
 * Return the effective pillar weight map for display — profile weights if active,
 * otherwise the base vacation weights (not stored catalog weights, which may be stale).
 */
export function getDisplayWeights(
  profile: TravelerProfile | null,
  tripType: string,
): Record<string, number> {
  if (profile) {
    const pw = PROFILE_WEIGHTS[profile]?.[tripType]
    if (pw) return pw
  }
  return BASE_VACATION_WEIGHTS[tripType] ?? {}
}
