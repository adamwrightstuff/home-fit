'use client'

import { useState } from 'react'
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
  const [copied, setCopied] = useState(false)

  // Copy scores summary to clipboard
  const copyScores = async () => {
    const lines = [
      `HomeFit Livability Score: ${location_info.city}, ${location_info.state} ${location_info.zip}`,
      `Total Score: ${total_score.toFixed(1)}/100`,
      '',
      'Pillar Scores:',
      ...Object.entries(livability_pillars).map(([key, pillar]) => 
        `  ${PILLAR_NAMES[key]}: ${pillar.score.toFixed(1)}/100`
      ),
    ]
    
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div className="space-y-6">
      {/* Location Info */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-homefit-text-primary mb-2">
              {location_info.city}, {location_info.state} {location_info.zip}
            </h2>
            <p className="text-homefit-text-secondary">Input: {data.input}</p>
            <p className="text-sm text-homefit-text-secondary opacity-75 mt-1">
              Coordinates: {data.coordinates.lat.toFixed(6)}, {data.coordinates.lon.toFixed(6)}
            </p>
          </div>
          <button
            onClick={copyScores}
            className="ml-4 px-4 py-2 bg-homefit-accent-primary text-white rounded-lg hover:opacity-90 transition-colors text-sm font-medium flex items-center gap-2 whitespace-nowrap"
          >
            {copied ? (
              <>
                <span>✓</span>
                <span>Copied!</span>
              </>
            ) : (
              <>
                <span>📋</span>
                <span>Copy Scores</span>
              </>
            )}
          </button>
        </div>
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
        <p className="text-sm text-homefit-text-secondary opacity-75">
          API Version: {metadata.version}
          {metadata.cache_hit && ' | (Cached)'}
        </p>
      </div>
    </div>
  )
}
