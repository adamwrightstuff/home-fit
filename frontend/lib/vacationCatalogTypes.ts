export type TripType = 'beach' | 'mountain' | 'city'

export interface VacationPillar {
  score: number | null
  weight: number
  confidence: number | null
}

export interface VacationPlace {
  key: string
  location: string
  trip_type: TripType
  total_score: number
  lat: number
  lon: number
  pillars: Record<string, VacationPillar>
  allocation_type: string | null
}

export interface VacationCatalogApiResponse {
  places: VacationPlace[]
}

export const TRIP_TYPE_LABEL: Record<TripType, string> = {
  beach: 'Beach',
  mountain: 'Mountain',
  city: 'City',
}

export const TRIP_TYPE_EMOJI: Record<TripType, string> = {
  beach: '🏖️',
  mountain: '🏔️',
  city: '🏙️',
}

export const VACATION_PILLAR_LABELS: Record<string, string> = {
  natural_beauty: 'Scenery',
  active_outdoors: 'Outdoor Activities',
  neighborhood_amenities: 'Food & Culture',
  air_travel_access: 'Getting There',
  climate_risk: 'Weather Risk',
  healthcare_access: 'Emergency Access',
}
