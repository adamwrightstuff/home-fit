'use client'

import { ScoreResponse } from '@/types/api'
import TotalScore from './TotalScore'
import PillarCard from './PillarCard'

interface ScoreDisplayProps {
  data: ScoreResponse
}

const PILLAR_NAMES: Record<string, string> = {
  active_outdoors: 'Active Outdoors',
  built_beauty: 'Built Beauty',
  natural_beauty: 'Natural Beauty',
  neighborhood_amenities: 'Neighborhood Amenities',
  air_travel_access: 'Air Travel Access',
  public_transit_access: 'Public Transit Access',
  healthcare_access: 'Healthcare Access',
  quality_education: 'Quality Education',
  housing_value: 'Housing Value',
}

const PILLAR_DESCRIPTIONS: Record<string, string> = {
  active_outdoors: 'Can I be active outside regularly?',
  built_beauty: 'Are the buildings cohesive, historic, and well-crafted?',
  natural_beauty: 'Is the landscape/tree canopy beautiful and calming?',
  neighborhood_amenities: 'Can I walk to great local spots?',
  air_travel_access: 'How easily can I fly somewhere?',
  public_transit_access: 'Can I get around without a car?',
  healthcare_access: 'Can I get medical care when needed?',
  quality_education: 'Can I raise kids with good schools?',
  housing_value: 'Can I afford a spacious home here?',
}

export default function ScoreDisplay({ data }: ScoreDisplayProps) {
  const { location_info, total_score, livability_pillars, overall_confidence, metadata } = data

  return (
    <div className="space-y-6">
      {/* Location Info */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          {location_info.city}, {location_info.state} {location_info.zip}
        </h2>
        <p className="text-gray-600">Input: {data.input}</p>
        <p className="text-sm text-gray-500 mt-1">
          Coordinates: {data.coordinates.lat.toFixed(6)}, {data.coordinates.lon.toFixed(6)}
        </p>
      </div>

      {/* Total Score */}
      <TotalScore score={total_score} confidence={overall_confidence} />

      {/* Pillars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(livability_pillars).map(([key, pillar]) => (
          <PillarCard
            key={key}
            name={PILLAR_NAMES[key] || key}
            description={PILLAR_DESCRIPTIONS[key] || ''}
            pillar={pillar}
          />
        ))}
      </div>

      {/* Metadata */}
      <div className="bg-white rounded-lg shadow-lg p-4">
        <p className="text-sm text-gray-500">
          API Version: {metadata.version}
          {metadata.cache_hit && ' | (Cached)'}
        </p>
      </div>
    </div>
  )
}
