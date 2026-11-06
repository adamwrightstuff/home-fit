import type { TripType } from '@/components/vacation/TripTypeSelector'
import type { TravelerProfile } from '@/components/vacation/TravelerProfileSelector'

const KEY = 'trovamo_vacation_prefs'

export interface VacationPrefs {
  tripType: TripType | null
  travelerProfile: TravelerProfile | null
}

/** One shared home for trip type and traveler profile, read by /vacation and /vacation/explorer. */
export function loadVacationPrefs(): VacationPrefs {
  try {
    const p = JSON.parse(localStorage.getItem(KEY) ?? '{}')
    return { tripType: p?.tripType ?? null, travelerProfile: p?.travelerProfile ?? null }
  } catch {
    return { tripType: null, travelerProfile: null }
  }
}

export function saveVacationPrefs(patch: Partial<VacationPrefs>): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...loadVacationPrefs(), ...patch }))
  } catch { /* storage unavailable: the choice still applies for this visit */ }
}
